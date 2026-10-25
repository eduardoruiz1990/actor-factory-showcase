"""Check a candidate's sample URLs against the target site's robots.txt.

Implements RFC 9309 matching, including the `*` and `$` wildcards that
Python's urllib.robotparser ignores: the longest matching rule wins, and Allow
wins a tie. Status handling follows RFC 9309 except where that would let a
check pass on missing information: 404/410 means no restrictions; other 4xx,
5xx and network errors leave the result unknown, which never passes Legality.
"""

import ipaddress
import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from factory.common.http import PoliteClient

log = logging.getLogger(__name__)

# fetch(origin) -> (HTTP status or None on network failure, body)
RobotsFetcher = Callable[[str], tuple[int | None, str]]


@dataclass
class RobotsResult:
    allowed: bool | None  # None: could not be determined
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow, path pattern)


class RobotsTxt:
    """A parsed robots.txt file."""

    def __init__(self, text: str) -> None:
        self._groups: list[_Group] = []
        current: _Group | None = None
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if current is None or not last_was_agent:
                    current = _Group()
                    self._groups.append(current)
                current.agents.append(value.lower())
                last_was_agent = True
            elif key in ("allow", "disallow"):
                last_was_agent = False
                if current is not None and value:  # an empty Disallow allows everything
                    current.rules.append((key == "allow", value))
            else:
                last_was_agent = False

    def allows(self, url: str, user_agent: str = "*") -> bool:
        parts = urlsplit(url)
        target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        best_length, allowed = -1, True
        for is_allow, pattern in self._rules_for(user_agent.lower()):
            if _matches(pattern, target):
                length = len(pattern)
                if length > best_length or (length == best_length and is_allow):
                    best_length, allowed = length, is_allow
        return allowed

    def _rules_for(self, agent: str) -> list[tuple[bool, str]]:
        token = agent.split("/", 1)[0]
        if token != "*":
            named = [g for g in self._groups if token in g.agents]
            if named:
                return [rule for g in named for rule in g.rules]
        return [rule for g in self._groups if "*" in g.agents for rule in g.rules]


def _matches(pattern: str, target: str) -> bool:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = ".*".join(re.escape(piece) for piece in body.split("*"))
    return re.match(regex + ("$" if anchored else ""), target) is not None


class RobotsChecker:
    def __init__(self, fetch: RobotsFetcher, user_agent: str = "*") -> None:
        self._fetch = fetch
        self._user_agent = user_agent
        self._cache: dict[str, tuple[int | None, RobotsTxt | None]] = {}

    def check(self, urls: list[str], fallback_domain: str = "") -> RobotsResult:
        targets = [u for u in urls if _public_http(u)] or (
            [f"https://{fallback_domain}/"] if fallback_domain and _public_http(f"https://{fallback_domain}/") else []
        )
        if not targets:
            return RobotsResult(None, "no public URL to check")
        notes = []
        for url in targets:
            parts = urlsplit(url)
            status, robots = self._robots(f"{parts.scheme or 'https'}://{parts.netloc}")
            if status in (404, 410):
                notes.append(f"{parts.netloc} has no robots.txt")
                continue
            if robots is None:
                reason = "unreachable" if status is None else f"HTTP {status}"
                return RobotsResult(None, f"robots.txt for {parts.netloc} could not be read ({reason})")
            if not robots.allows(url, self._user_agent):
                return RobotsResult(False, f"robots.txt disallows {parts.path or '/'} on {parts.netloc}")
            notes.append(f"robots.txt allows {parts.path or '/'} on {parts.netloc}")
        return RobotsResult(True, "; ".join(dict.fromkeys(notes)))

    def _robots(self, origin: str) -> tuple[int | None, RobotsTxt | None]:
        if origin not in self._cache:
            status, body = self._fetch(origin)
            self._cache[origin] = (status, RobotsTxt(body) if status == 200 else None)
        return self._cache[origin]


def _public_http(url: str) -> bool:
    """Only plain public hostnames: the URLs come from model output and must not reach internal hosts."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or "." not in host or host.endswith((".local", ".internal")):
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host != "localhost"
    return False


def live_fetcher(http: PoliteClient) -> RobotsFetcher:
    def fetch(origin: str) -> tuple[int | None, str]:
        try:
            response = http.get(f"{origin}/robots.txt")
        except httpx.HTTPError as exc:
            log.warning("robots.txt for %s: %s", origin, exc)
            return None, ""
        return response.status_code, response.text

    return fetch


def fixture_fetcher(robots_dir: Path) -> RobotsFetcher:
    """tests/fixtures/robots/<host>.txt is served as 200, <host>.404 as a 404; anything else is unreachable."""

    def fetch(origin: str) -> tuple[int | None, str]:
        host = urlsplit(origin).netloc
        if (robots_dir / f"{host}.txt").exists():
            return 200, (robots_dir / f"{host}.txt").read_text(encoding="utf-8")
        if (robots_dir / f"{host}.404").exists():
            return 404, ""
        return None, ""

    return fetch


class SavedRobots:
    """Serves the robots.txt results of an earlier run's validation.json, so a re-render matches that run."""

    def __init__(self, path: Path) -> None:
        records = json.loads(path.read_text(encoding="utf-8"))
        self._results = {
            tuple(r["assessment"]["sample_urls"]): RobotsResult(**r["robots"])
            for r in records if r.get("assessment") and r.get("robots")
        }

    def check(self, urls: list[str], fallback_domain: str = "") -> RobotsResult:
        return self._results.get(tuple(urls), RobotsResult(None, "robots.txt result not in the reused run"))

