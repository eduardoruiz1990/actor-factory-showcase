"""Save one real response from the source as a test fixture, politely.

The Builder uses this to fetch one or two real responses for tests/fixtures/
(a summarising web-fetch tool does not return the raw response). It goes
through the Actor's own PoliteClient (rate limit, retries with back-off) and
robots.txt check, and passes the response through the privacy guard before
saving it. Names in free text are not removed: read the file before committing.
Usage, from the Actor's folder: python -m tests.fetch_fixture <url> tests/fixtures/<name>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from httpx2 import AsyncBaseTransport

from my_actor.polite import PoliteClient
from my_actor.privacy import clean
from my_actor.robots import RobotsCache

FIXTURES = Path('tests') / 'fixtures'
MAX_CHARS = 1_000_000  # a fixture should be one small page; ask the source for fewer results if it is bigger


async def fetch(url: str, out: Path, transport: AsyncBaseTransport | None = None) -> int:
    if FIXTURES.resolve() not in out.resolve().parents:
        print(f'{out} is outside {FIXTURES}/; nothing saved', file=sys.stderr)
        return 1
    async with PoliteClient(transport=transport) as http:
        if not await RobotsCache(http).allowed(url):
            print(f'robots.txt does not allow {url} (or could not be read); nothing saved', file=sys.stderr)
            return 1
        response = await http.get(url)
    if response.status_code != 200:
        print(f'{url} returned HTTP {response.status_code}; nothing saved', file=sys.stderr)
        return 1
    if len(response.text) > MAX_CHARS:
        print(f'{url} returned {len(response.text)} characters; ask for fewer results', file=sys.stderr)
        return 1
    try:
        text = json.dumps(clean(response.json()), indent=2, ensure_ascii=False)
    except ValueError:
        text = clean(response.text)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + '\n', encoding='utf-8')
    content_type = response.headers.get('content-type', 'unknown type')
    print(f'saved {url} -> {out} ({len(text)} characters, {content_type}); check it for names before committing')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('url')
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    return asyncio.run(fetch(args.url, args.out))


if __name__ == '__main__':
    sys.exit(main())
