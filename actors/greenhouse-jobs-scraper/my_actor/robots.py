"""robots.txt: fetched once per site, matched with RFC 9309 rules (including * and $).

Python's urllib.robotparser ignores the wildcards, so the matcher is written here.
Status handling follows RFC 9309: a 4xx answer (404, but also 401 or 403 from an
API that publishes no file) means there is no robots.txt, so nothing is
disallowed (Q19). 429, 5xx and network errors mean robots.txt is unreachable, and
the Actor treats the whole site as disallowed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from apify import Actor
from httpx2 import HTTPError

from .polite import PoliteClient


@dataclass
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow, path pattern)


class RobotsTxt:
    def __init__(self, text: str) -> None:
        self._groups: list[_Group] = []
        current: _Group | None = None
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split('#', 1)[0].strip()
            if ':' not in line:
                continue
            key, value = (part.strip() for part in line.split(':', 1))
            key = key.lower()
            if key == 'user-agent':
                if current is None or not last_was_agent:
                    current = _Group()
                    self._groups.append(current)
                current.agents.append(value.lower())
                last_was_agent = True
            elif key in ('allow', 'disallow'):
                last_was_agent = False
                if current is not None and value:  # an empty Disallow allows everything
                    current.rules.append((key == 'allow', value))
            else:
                last_was_agent = False

    def allows(self, url: str, user_agent: str) -> bool:
        parts = urlsplit(url)
        target = (parts.path or '/') + (f'?{parts.query}' if parts.query else '')
        best_length, allowed = -1, True
        for is_allow, pattern in self._rules_for(_product_token(user_agent)):
            if _matches(pattern, target):
                length = len(pattern)
                if length > best_length or (length == best_length and is_allow):
                    best_length, allowed = length, is_allow
        return allowed

    def _rules_for(self, token: str) -> list[tuple[bool, str]]:
        named = [g for g in self._groups if token in g.agents]
        if named:
            return [rule for g in named for rule in g.rules]
        return [rule for g in self._groups if '*' in g.agents for rule in g.rules]


def _product_token(user_agent: str) -> str:
    """'Mozilla/5.0 (compatible; ActorFactoryBot/0.1; ...)' -> 'actorfactorybot'."""
    match = re.search(r'compatible;\s*([A-Za-z0-9_-]+)', user_agent)
    token = match.group(1) if match else user_agent.split('/', 1)[0]
    return token.lower()


def _matches(pattern: str, target: str) -> bool:
    anchored = pattern.endswith('$')
    body = pattern[:-1] if anchored else pattern
    regex = '.*'.join(re.escape(piece) for piece in body.split('*'))
    return re.match(regex + ('$' if anchored else ''), target) is not None


class RobotsCache:
    """Answers 'may the Actor fetch this URL?', reading each site's robots.txt once."""

    def __init__(self, http: PoliteClient) -> None:
        self._http = http
        self._sites: dict[str, RobotsTxt | None] = {}  # None: disallow the whole site

    async def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or not parts.netloc:
            return False
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self._sites:
            self._sites[origin] = await self._load(origin)
        robots = self._sites[origin]
        return robots is not None and robots.allows(url, self._http.user_agent)

    async def _load(self, origin: str) -> RobotsTxt | None:
        try:
            response = await self._http.get(f'{origin}/robots.txt')
        except HTTPError as exc:
            Actor.log.warning(f'robots.txt for {origin} unreachable ({exc!r}); skipping the site')
            return None
        if response.status_code == 200:
            return RobotsTxt(response.text)
        if 400 <= response.status_code < 500 and response.status_code != 429:
            return RobotsTxt('')  # RFC 9309 2.3.1.3: robots.txt is unavailable, so nothing is disallowed
        Actor.log.warning(f'robots.txt for {origin} returned {response.status_code}; skipping the site')
        return None
