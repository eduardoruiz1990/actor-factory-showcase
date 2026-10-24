import asyncio

import httpx2
import pytest

from my_actor.polite import PoliteClient
from my_actor.robots import RobotsCache, RobotsTxt

UA = 'Mozilla/5.0 (compatible; ActorFactoryBot/0.1; +https://apify.com)'
ROBOTS = """\
User-agent: ActorFactoryBot
Disallow: /private-for-us

User-agent: *
Disallow: /private
Allow: /private/public
Disallow: /*.json$
"""


@pytest.mark.parametrize(
    ('url', 'allowed'),
    [
        ('https://x.com/private/file', True),  # our named group replaces the * group
        ('https://x.com/private-for-us/a', False),
    ],
)
def test_named_group_applies_to_our_bot(url, allowed):
    assert RobotsTxt(ROBOTS).allows(url, UA) is allowed


@pytest.mark.parametrize(
    ('url', 'allowed'),
    [
        ('https://x.com/', True),
        ('https://x.com/private/file', False),
        ('https://x.com/private/public/page', True),
        ('https://x.com/data/items.json', False),
        ('https://x.com/data/items.json?page=2', True),
    ],
)
def test_star_group_with_wildcards(url, allowed):
    assert RobotsTxt(ROBOTS).allows(url, 'SomeOtherBot/1.0') is allowed


async def _no_sleep(_seconds):
    return None


def cache(handler):
    http = PoliteClient(min_interval=0, max_retries=0, user_agent=UA, transport=httpx2.MockTransport(handler), sleep=_no_sleep)
    return RobotsCache(http)


def test_404_allows_and_errors_disallow():
    def handler(request):
        if request.url.host == 'open.example':
            return httpx2.Response(404)
        if request.url.host == 'down.example':
            return httpx2.Response(503)
        raise httpx2.ConnectError('boom', request=request)

    robots = cache(handler)

    async def run():
        return (await robots.allowed('https://open.example/a'), await robots.allowed('https://down.example/a'),
                await robots.allowed('https://gone.example/a'), await robots.allowed('ftp://open.example/a'))

    assert asyncio.run(run()) == (True, False, False, False)


def test_robots_is_fetched_once_per_site():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx2.Response(200, text='User-agent: *\nDisallow: /b\n')

    robots = cache(handler)

    async def run():
        return [await robots.allowed(u) for u in ('https://x.example/a', 'https://x.example/b', 'https://x.example/c')]

    assert asyncio.run(run()) == [True, False, True]
    assert calls == ['https://x.example/robots.txt']
