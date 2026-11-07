"""Polite async HTTP: a per-host rate limit and retries with exponential back-off.

Every request the Actor makes goes through PoliteClient. Keep it that way:
the factory's rules require polite rate limits and retries with back-off.
"""

from __future__ import annotations

import asyncio
import email.utils
import random
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from apify import Actor
from httpx2 import AsyncBaseTransport, AsyncClient, Response, TransportError

# Timeouts, rate limits and server-side errors are worth retrying; other statuses are returned as they are.
RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
USER_AGENT = 'Mozilla/5.0 (compatible; ActorFactoryBot/0.1; +https://apify.com)'


class PoliteClient:
    def __init__(
        self,
        *,
        min_interval: float = 1.0,
        max_retries: int = 4,
        backoff_base: float = 2.0,
        backoff_max: float = 60.0,
        timeout: float = 30.0,
        user_agent: str = USER_AGENT,
        transport: AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = AsyncClient(
            timeout=timeout, headers={'User-Agent': user_agent}, follow_redirects=True, transport=transport
        )
        self.user_agent = user_agent
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._sleep = sleep
        self._clock = clock
        self._next_slot: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get(self, url: str, **kwargs: Any) -> Response:
        """GET with retries. Returns the last response once retries run out; raises the last network error."""
        host = urlsplit(url).netloc
        for attempt in range(self._max_retries + 1):
            await self._wait_for_turn(host)
            try:
                response = await self._client.get(url, **kwargs)
            except TransportError as exc:
                if attempt == self._max_retries:
                    raise
                delay = self._backoff(attempt)
                Actor.log.warning(f'GET {url} failed ({exc!r}); retry {attempt + 1} in {delay:.1f}s')
            else:
                if response.status_code not in RETRY_STATUSES or attempt == self._max_retries:
                    return response
                delay = self._retry_after(response)
                if delay is not None and delay > self._backoff_max:
                    # Asked to wait longer than we would: give up now rather than come back too soon.
                    Actor.log.warning(f'GET {url} returned {response.status_code} and asked to wait {delay:.0f}s; not retrying')
                    return response
                if delay is None:
                    delay = self._backoff(attempt)
                Actor.log.warning(f'GET {url} returned {response.status_code}; retry {attempt + 1} in {delay:.1f}s')
            await self._sleep(delay)
        raise AssertionError('unreachable')

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> PoliteClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _wait_for_turn(self, host: str) -> None:
        # One lock per host keeps concurrent tasks from sending to the same site faster than the limit.
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = self._clock()
            slot = self._next_slot.get(host, now)
            if slot > now:
                await self._sleep(slot - now)
            self._next_slot[host] = max(slot, now) + self._min_interval

    def _backoff(self, attempt: int) -> float:
        delay = self._backoff_base * (2**attempt) + random.uniform(0, self._backoff_base)
        return min(delay, self._backoff_max)

    def _retry_after(self, response: Response) -> float | None:
        value = response.headers.get('Retry-After')
        if not value:
            return None
        try:
            seconds = float(value)
        except ValueError:
            try:
                when = email.utils.parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            seconds = (when - datetime.now(UTC)).total_seconds()
        return max(seconds, 0.0)
