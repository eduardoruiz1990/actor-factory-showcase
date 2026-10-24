import httpx
import pytest

from factory.common.http import PoliteClient


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(handler, clock, **kwargs):
    return PoliteClient(
        user_agent="test-agent",
        min_interval=1.0,
        max_retries=kwargs.pop("max_retries", 3),
        backoff_base=2.0,
        backoff_max=60.0,
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        clock=clock.time,
        **kwargs,
    )


def test_retries_server_errors_with_exponential_backoff():
    clock = FakeClock()
    statuses = iter([503, 502, 200])

    def handler(request):
        return httpx.Response(next(statuses), json={"ok": True})

    client = make_client(handler, clock)
    response = client.get("https://api.example.com/x")
    assert response.status_code == 200
    # Two back-offs: 2-4 s, then 4-6 s (base * 2**attempt plus jitter up to base).
    backoffs = [s for s in clock.sleeps if s > 1.0]
    assert len(backoffs) == 2
    assert 2.0 <= backoffs[0] <= 4.0
    assert 4.0 <= backoffs[1] <= 6.0


def test_honours_retry_after_header():
    clock = FakeClock()
    responses = iter([httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200)])
    client = make_client(lambda request: next(responses), clock)
    assert client.get("https://api.example.com/x").status_code == 200
    assert 7.0 in clock.sleeps


def test_does_not_retry_client_errors():
    clock = FakeClock()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404)

    client = make_client(handler, clock)
    assert client.get("https://api.example.com/missing").status_code == 404
    assert len(calls) == 1


def test_returns_last_response_when_retries_run_out():
    clock = FakeClock()
    client = make_client(lambda request: httpx.Response(500), clock, max_retries=2)
    assert client.get("https://api.example.com/x").status_code == 500


def test_network_errors_are_retried_then_raised():
    clock = FakeClock()
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("boom", request=request)

    client = make_client(handler, clock, max_retries=2)
    with pytest.raises(httpx.ConnectError):
        client.get("https://api.example.com/x")
    assert len(calls) == 3


def test_rate_limits_each_host_separately():
    clock = FakeClock()
    client = make_client(lambda request: httpx.Response(200), clock)
    client.get("https://a.example.com/1")
    client.get("https://b.example.com/1")  # different host: no wait
    assert clock.sleeps == []
    client.get("https://a.example.com/2")  # same host, no time passed: waits the full interval
    assert clock.sleeps == [1.0]


def test_sends_user_agent():
    seen = {}

    def handler(request):
        seen["ua"] = request.headers["User-Agent"]
        return httpx.Response(200)

    make_client(handler, FakeClock()).get("https://a.example.com/")
    assert seen["ua"] == "test-agent"


def test_from_config_reads_http_section(config):
    client = PoliteClient.from_config(config)
    assert client._min_interval == config["http"]["min_interval_seconds"]
    assert client._max_retries == config["http"]["max_retries"]
