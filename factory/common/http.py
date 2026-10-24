"""A polite HTTP client: per-host rate limit, retries with exponential back-off.

Every outbound request the factory makes goes through PoliteClient, so the
politeness rules in config.yaml (http section) apply everywhere.
"""

import email.utils
import logging
import random
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)

# Statuses worth retrying: timeouts, rate limits and server-side errors.
RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class PoliteClient:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float = 30.0,
        min_interval: float = 1.0,
        max_retries: int = 4,
        backoff_base: float = 2.0,
        backoff_max: float = 60.0,
        headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent, **(headers or {})},
            transport=transport,
            follow_redirects=True,
        )
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._sleep = sleep
        self._clock = clock
        self._rng = rng or random.Random()
        self._last_request_at: dict[str, float] = {}

    @classmethod
    def from_config(cls, config: dict[str, Any], **overrides: Any) -> "PoliteClient":
        http_cfg = config["http"]
        kwargs: dict[str, Any] = {
            "user_agent": http_cfg["user_agent"],
            "timeout": float(http_cfg["timeout_seconds"]),
            "min_interval": float(http_cfg["min_interval_seconds"]),
            "max_retries": int(http_cfg["max_retries"]),
            "backoff_base": float(http_cfg["backoff_base_seconds"]),
            "backoff_max": float(http_cfg["backoff_max_seconds"]),
        }
        kwargs.update(overrides)
        return cls(**kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a request, retrying on network errors and RETRY_STATUSES.

        Returns the last response (which may be an error status) once retries
        run out; raises the last network error if every attempt failed to connect.
        """
        host = urlsplit(url).netloc
        for attempt in range(self._max_retries + 1):
            self._wait_for_turn(host)
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise
                delay = self._backoff(attempt)
                log.warning("%s %s failed (%s); retry %d in %.1fs", method, url, exc, attempt + 1, delay)
            else:
                if response.status_code not in RETRY_STATUSES or attempt == self._max_retries:
                    return response
                delay = self._retry_after(response)
                if delay is None:
                    delay = self._backoff(attempt)
                log.warning(
                    "%s %s returned %d; retry %d in %.1fs",
                    method, url, response.status_code, attempt + 1, delay,
                )
            self._sleep(delay)
        raise AssertionError("unreachable")

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        response = self.get(url, **kwargs)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _wait_for_turn(self, host: str) -> None:
        last = self._last_request_at.get(host)
        if last is not None:
            wait = last + self._min_interval - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last_request_at[host] = self._clock()

    def _backoff(self, attempt: int) -> float:
        delay = self._backoff_base * (2**attempt) + self._rng.uniform(0, self._backoff_base)
        return min(delay, self._backoff_max)

    def _retry_after(self, response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
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
                when = when.replace(tzinfo=timezone.utc)
            seconds = (when - datetime.now(timezone.utc)).total_seconds()
        return min(max(seconds, 0.0), self._backoff_max)
