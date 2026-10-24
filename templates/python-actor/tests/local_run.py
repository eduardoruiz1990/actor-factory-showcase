"""Run one local Actor collection against a fake website; used by test_main in a fresh process.

The Apify SDK keeps its configuration and storage settings for the life of the
process, so every end-to-end test runs in its own interpreter, like a real run.
Usage: python -m tests.local_run '<settings json>'  -> prints {"pushed": n}
"""

import asyncio
import json
import sys

import httpx2
from apify import Actor

from my_actor import main as actor_main
from my_actor.polite import PoliteClient
from my_actor.source import Settings

PAGE = (
    '<html lang="en"><head><title>Example {n}</title><meta name="description" content="Page {n}. '
    'Contact sales@example.com"></head><body><h1>Hi</h1></body></html>'
)


def site(request: httpx2.Request) -> httpx2.Response:
    if request.url.path == '/robots.txt':
        return httpx2.Response(200, text='User-agent: *\nDisallow: /blocked\n')
    return httpx2.Response(200, text=PAGE.format(n=request.url.path.strip('/')))


async def _no_sleep(_seconds: float) -> None:
    return None


async def run(settings: Settings) -> int:
    http = PoliteClient(min_interval=0, transport=httpx2.MockTransport(site), sleep=_no_sleep)
    async with Actor(exit_process=False):
        pushed = await actor_main.collect(settings, http=http)
    await http.aclose()
    return pushed


if __name__ == '__main__':
    settings = Settings(**json.loads(sys.argv[1]))
    print(json.dumps({'pushed': asyncio.run(run(settings))}))
