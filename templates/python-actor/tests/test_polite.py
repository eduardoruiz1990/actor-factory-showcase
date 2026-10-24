import asyncio

import httpx2
import pytest

from my_actor.polite import PoliteClient


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def client(handler, clock, **kwargs):
    return PoliteClient(min_interval=1.0, max_retries=kwargs.pop('max_retries', 3), backoff_base=2.0,
                        transport=httpx2.MockTransport(handler), sleep=clock.sleep, clock=clock.time, **kwargs)


def test_retries_server_errors_with_backoff():
    clock = FakeClock()
    statuses = iter([503, 502, 200])
    http = client(lambda r: httpx2.Response(next(statuses)), clock)
    assert asyncio.run(http.get('https://a.example/')).status_code == 200
    backoffs = [s for s in clock.sleeps if s > 1.0]
    assert len(backoffs) == 2 and 2.0 <= backoffs[0] <= 4.0 and 4.0 <= backoffs[1] <= 6.0


def test_honours_retry_after():
    clock = FakeClock()
    responses = iter([httpx2.Response(429, headers={'Retry-After': '7'}), httpx2.Response(200)])
    http = client(lambda r: next(responses), clock)
    assert asyncio.run(http.get('https://a.example/')).status_code == 200
    assert 7.0 in clock.sleeps


def test_client_errors_are_not_retried():
    clock = FakeClock()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(404)

    assert asyncio.run(client(handler, clock).get('https://a.example/x')).status_code == 404
    assert len(calls) == 1


def test_network_errors_are_retried_then_raised():
    clock = FakeClock()
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx2.ConnectError('boom', request=request)

    with pytest.raises(httpx2.ConnectError):
        asyncio.run(client(handler, clock, max_retries=2).get('https://a.example/'))
    assert len(calls) == 3


def test_rate_limit_is_per_host():
    clock = FakeClock()
    http = client(lambda r: httpx2.Response(200), clock)

    async def run():
        await http.get('https://a.example/1')
        await http.get('https://b.example/1')
        await http.get('https://a.example/2')

    asyncio.run(run())
    assert clock.sleeps == [1.0]


def test_sends_the_bot_user_agent():
    seen = {}

    def handler(request):
        seen['ua'] = request.headers['User-Agent']
        return httpx2.Response(200)

    asyncio.run(client(handler, FakeClock()).get('https://a.example/'))
    assert 'ActorFactoryBot' in seen['ua']
