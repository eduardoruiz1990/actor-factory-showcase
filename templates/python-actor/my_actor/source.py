"""The niche-specific part: which requests to make and how to turn responses into results.

The Builder replaces this file for each Actor. The example reads public pages
and returns their title, description and language. Keep the contract:
iter_items() yields plain dicts, fetches only through `http`, and asks
`robots` before every URL it fetches from a website. (An official API with its
own terms and no robots.txt may skip the robots check; say so in the README.)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from apify import Actor
from bs4 import BeautifulSoup

from .polite import PoliteClient
from .robots import RobotsCache


@dataclass
class Settings:
    start_urls: list[str]
    max_results: int
    max_requests_per_second: float

    @classmethod
    def from_input(cls, actor_input: dict[str, Any]) -> Settings:
        urls = [s.get('url') if isinstance(s, dict) else s for s in actor_input.get('startUrls') or []]
        urls = [u.strip() for u in urls if isinstance(u, str) and u.strip()]
        if not urls:
            raise ValueError('Input needs at least one start URL in "startUrls".')
        max_results = int(actor_input.get('maxResults') or 100)
        rate = float(actor_input.get('maxRequestsPerSecond') or 1)
        return cls(start_urls=urls, max_results=max(1, max_results), max_requests_per_second=min(max(rate, 0.1), 5.0))


async def iter_items(settings: Settings, http: PoliteClient, robots: RobotsCache) -> AsyncIterator[dict[str, Any]]:
    for url in settings.start_urls:
        if not await robots.allowed(url):
            Actor.log.warning(f'robots.txt does not allow {url}; skipped')
            continue
        response = await http.get(url)
        if response.status_code != 200:
            Actor.log.warning(f'{url} returned HTTP {response.status_code}; skipped')
            continue
        yield parse_page(str(response.url), response.text)


def parse_page(url: str, html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, 'lxml')
    title = soup.title.get_text(strip=True) if soup.title else None
    description_tag = soup.find('meta', attrs={'name': 'description'})
    description = description_tag.get('content') if description_tag else None
    language = soup.html.get('lang') if soup.html else None
    return {
        'url': url,
        'title': title or None,
        'description': (description or '').strip() or None,
        'language': language or None,
        'fetchedAt': datetime.now(UTC).isoformat(timespec='seconds'),
    }
