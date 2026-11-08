"""Build the job directory (QUESTIONS Q29), so a search can run without naming companies.

Run by .github/workflows/directory.yml, not by the Actor, with the Actor's own
source code so robots.txt, rate limits and parsing stay the same:

    python -m tools.build_directory verify tools/companies.txt out/boards.json
    python -m tools.build_directory index out/boards.json out/index.json out/index.json.gz

`verify` tries each company name on all five platforms and keeps the board with
the most open jobs. `index` records each board's job titles and locations, no
descriptions, for a search to pick which boards to read live. A board that does
not answer (a 429, a failure, robots.txt) is "not read": it keeps its last entry.

A platform that keeps answering 429 is left alone for the rest of the run, and each
platform has a time budget, so one platform cannot cost the others' results.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from httpx2 import HTTPError, Response

from my_actor import privacy, source
from my_actor.polite import PoliteClient
from my_actor.robots import RobotsCache

PREFIXES = ('', 'lever:', 'ashby:', 'workable:', 'personio:')
# Seconds between requests to one host. Workable answered 429 at one per second (Q29).
INTERVALS = {'workable': 5.0}
DEFAULT_INTERVAL = 1.0
# A 429 asks us to stop: after this many in a row, the platform is left alone for the rest of the run.
MAX_429_IN_A_ROW = 3
RETRIES = 1
PLATFORM_BUDGET_SECONDS = 45 * 60
# The owner's contract rules out pharma and health (Q29). The list leaves them out; this catches a namesake.
EXCLUDED = re.compile(
    r'pharma|health|biotech|therapeutic|medic|clinic|hospital|biolog|bioscience|drug|krankenversicherung', re.I
)
# Lever and Ashby boards carry no company name, so a health company under a harmless name gets past EXCLUDED.
# These boards were found that way; verify never keeps them and the daily build drops them from a kept boards.json.
# lever:arcadia is Arcadia.io, a health data company (Medicaid, payor, life sciences), not the energy company listed.
EXCLUDED_BOARDS = frozenset({'lever:arcadia'})

Client = Callable[[float], PoliteClient]


class TooManyRequests(Exception):
    """A platform keeps answering 429."""


class DirectoryClient(PoliteClient):
    """A polite client that raises TooManyRequests after MAX_429_IN_A_ROW rate-limit answers in a row."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._refused = 0

    async def get(self, url: str, **kwargs: Any) -> Response:
        response = await super().get(url, **kwargs)
        self._refused = self._refused + 1 if response.status_code == 429 else 0
        if self._refused >= MAX_429_IN_A_ROW:
            raise TooManyRequests(url)
        return response


def default_client(interval: float) -> PoliteClient:
    return DirectoryClient(min_interval=interval, max_retries=RETRIES)


def platform_of(key: str) -> str:
    return key.partition(':')[0] if ':' in key else 'greenhouse'


def read_names(text: str) -> list[str]:
    """The names in companies.txt, once each, without comments."""
    names = (name for line in text.splitlines() if not line.startswith('#') for name in line.split())
    return list(dict.fromkeys(name.lower() for name in names))


def excluded(*names: Any) -> bool:
    return any(EXCLUDED.search(name) for name in names if isinstance(name, str))


async def read_board(key: str, http: PoliteClient, robots: RobotsCache) -> list[dict[str, Any]] | None:
    """A board's open jobs, or None when it did not answer."""
    settings = source.Settings(board_tokens=[key], max_results=10**7, max_requests_per_second=1.0,
                               include_content=False)
    read: set[str] = set()
    try:
        jobs = [privacy.clean(job) async for job in source.iter_items(settings, http, robots, read)]
    except HTTPError as exc:
        print(f'{key} could not be reached ({exc!r}); skipped')
        return None
    return jobs if read else None


async def scan(keys: list[str], client: Client = default_client,
               budget: float = PLATFORM_BUDGET_SECONDS) -> dict[str, list[dict[str, Any]] | None]:
    """Read every board: in turn within a platform, side by side across platforms, so a slow one holds up no other.

    A platform that stops early (too many 429s, or out of time) leaves its remaining boards out of the result.
    """
    by_platform: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        by_platform[platform_of(key)].append(key)
    results: dict[str, list[dict[str, Any]] | None] = {}

    async def read_platform(platform: str, boards: list[str]) -> None:
        async with client(INTERVALS.get(platform, DEFAULT_INTERVAL)) as http:
            robots = RobotsCache(http)
            for key in boards:
                results[key] = await read_board(key, http, robots)

    async def read_within_limits(platform: str, boards: list[str]) -> None:
        try:
            await asyncio.wait_for(read_platform(platform, boards), budget)
        except TooManyRequests:
            reason = f'answered 429 {MAX_429_IN_A_ROW} times in a row'
        except TimeoutError:
            reason = f'ran out of its {budget / 60:.0f} minutes'
        else:
            return
        left = sum(1 for key in boards if key not in results)
        print(f'{platform} {reason}; stopped with {left} of {len(boards)} boards not tried')

    await asyncio.gather(*(read_within_limits(platform, boards) for platform, boards in by_platform.items()))
    return results


async def verify(names: list[str], client: Client = default_client) -> dict[str, Any]:
    """{'boards': {key: company}}: for each name, the board with the most open jobs, without excluded companies."""
    tries = {name: [key for prefix in PREFIXES if (key := source.board_key(prefix + name))] for name in names}
    results = await scan(list(dict.fromkeys(key for keys in tries.values() for key in keys)), client)
    boards: dict[str, str | None] = {}
    found = 0
    for name, keys in tries.items():
        live = [key for key in keys if results.get(key)]
        if not live:
            continue
        found += 1
        best = max(live, key=lambda key: len(results[key] or []))
        company = (results[best] or [{}])[0].get('company')
        if not excluded(name, company) and best not in EXCLUDED_BOARDS:
            boards[best] = company
    unread = sum(1 for jobs in results.values() if jobs is None)
    print(f'{found} of {len(names)} names have open jobs; {len(boards)} boards kept; '
          f'{unread} board tries got no answer or are unknown')
    return {'boards': boards}


async def build_index(boards: dict[str, str | None], previous: dict[str, Any], now: datetime,
                      client: Client = default_client) -> dict[str, Any]:
    """{'built_at', 'boards': {key: {'company', 'jobs': [[title, location], ...]}}}; unread boards stay as they were."""
    boards = {key: company for key, company in boards.items() if key not in EXCLUDED_BOARDS}
    results = await scan(list(boards), client)
    index: dict[str, Any] = {}
    unread = 0
    for key, company in boards.items():
        jobs = results.get(key)
        if jobs is None:
            unread += 1
            if key in previous:
                index[key] = previous[key]
        elif jobs:
            index[key] = {'company': company or jobs[0].get('company'),
                          'jobs': [[job.get('title'), job.get('location')] for job in jobs]}
    total = sum(len(entry['jobs']) for entry in index.values())
    print(f'{len(index)} boards, {total} jobs; {unread} of {len(boards)} boards not read this time')
    return {'built_at': now.isoformat(timespec='seconds'), 'boards': index}


def main(argv: list[str]) -> int:
    command, *paths = argv
    if command == 'verify':
        names = read_names(Path(paths[0]).read_text(encoding='utf-8'))
        Path(paths[1]).write_text(json.dumps(asyncio.run(verify(names))), encoding='utf-8')
        return 0
    if command == 'index':
        boards = json.loads(Path(paths[0]).read_text(encoding='utf-8'))['boards']
        last = Path(paths[1])
        previous = json.loads(last.read_text(encoding='utf-8')).get('boards', {}) if last.exists() else {}
        index = asyncio.run(build_index(boards, previous, datetime.now(UTC)))
        data = gzip.compress(json.dumps(index, ensure_ascii=False, separators=(',', ':')).encode(), mtime=0)
        Path(paths[2]).write_bytes(data)
        print(f'index: {len(data) / 1e6:.2f} MB compressed')
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
