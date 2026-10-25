"""Greenhouse job boards: every open job on a company's board, read from the official Job Board API.

One request per board: GET boards-api.greenhouse.io/v1/boards/<token>/jobs?content=true
returns all open jobs with their departments, offices and description. The API
is public and needs no key. Every URL is still checked against the API host's
robots.txt before it is fetched. Keep the contract: iter_items() yields plain
dicts and fetches only through `http`.
"""

from __future__ import annotations

import html
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlsplit

from apify import Actor
from bs4 import BeautifulSoup

from .polite import PoliteClient
from .robots import RobotsCache

API = 'https://boards-api.greenhouse.io/v1/boards'
# Board pages people copy from the browser: boards.greenhouse.io/<token>, job-boards.greenhouse.io/<token>,
# job-boards.eu.greenhouse.io/<token>, boards-api.greenhouse.io/v1/boards/<token>/..., or ?for=<token>.
_TOKEN = re.compile(r'^[A-Za-z0-9_.-]+$')
_BLOCKS = ['p', 'div', 'li', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'tr', 'blockquote']


@dataclass
class Settings:
    board_tokens: list[str]
    max_results: int
    max_requests_per_second: float
    include_content: bool = True
    title_keywords: list[str] = field(default_factory=list)
    location_keywords: list[str] = field(default_factory=list)

    @classmethod
    def from_input(cls, actor_input: dict[str, Any]) -> Settings:
        tokens: list[str] = []
        for raw in actor_input.get('boardTokens') or []:
            token = board_token(raw.get('url') if isinstance(raw, dict) else raw)
            if token is None:
                Actor.log.warning(f'{raw!r} is not a Greenhouse board token or greenhouse.io URL; skipped')
            elif token not in tokens:
                tokens.append(token)
        if not tokens:
            raise ValueError('Input needs at least one Greenhouse board token in "boardTokens" (for example "airbnb").')
        max_results = int(actor_input.get('maxResults') or 1000)
        rate = float(actor_input.get('maxRequestsPerSecond') or 1)
        return cls(
            board_tokens=tokens,
            max_results=max(1, max_results),
            max_requests_per_second=min(max(rate, 0.1), 5.0),
            include_content=actor_input.get('includeContent', True) is not False,
            title_keywords=_keywords(actor_input.get('titleKeywords')),
            location_keywords=_keywords(actor_input.get('locationKeywords')),
        )


def board_token(value: Any) -> str | None:
    """'airbnb', 'https://boards.greenhouse.io/airbnb' or 'https://job-boards.greenhouse.io/airbnb/jobs/1' -> 'airbnb'."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if '/' in value or '.' in value:
        parts = urlsplit(value if '://' in value else f'https://{value}')
        host = (parts.hostname or '').lower()
        if host != 'greenhouse.io' and not host.endswith('.greenhouse.io'):
            return None  # a company's own careers page does not show its board token
        query_token = re.search(r'(?:^|&)for=([^&]+)', parts.query)
        if query_token:
            value = query_token.group(1)
        else:
            path = [p for p in parts.path.split('/') if p]
            if path[:2] == ['v1', 'boards']:
                path = path[2:]
            if path[:1] == ['embed']:
                path = path[1:]
            value = path[0] if path else ''
    value = value.lower()
    return value if _TOKEN.match(value) else None


def _keywords(value: Any) -> list[str]:
    if isinstance(value, str):
        value = value.split(',')
    if not isinstance(value, list):
        return []
    return [k.strip().lower() for k in value if isinstance(k, str) and k.strip()]


async def iter_items(settings: Settings, http: PoliteClient, robots: RobotsCache) -> AsyncIterator[dict[str, Any]]:
    for token in settings.board_tokens:
        url = f'{API}/{quote(token)}/jobs' + ('?content=true' if settings.include_content else '')
        if not await robots.allowed(url):
            Actor.log.warning(f'robots.txt does not allow {url}; skipped')
            continue
        response = await http.get(url)
        if response.status_code == 404:
            Actor.log.warning(f'No Greenhouse board called "{token}" (HTTP 404); skipped')
            continue
        if response.status_code != 200:
            Actor.log.warning(f'Board "{token}" returned HTTP {response.status_code}; skipped')
            continue
        try:
            jobs = parse_jobs(token, response.json())
        except ValueError as exc:
            Actor.log.warning(f'Board "{token}" sent a response that could not be read ({exc}); skipped')
            continue
        Actor.log.info(f'Board "{token}": {len(jobs)} open job(s)')
        if any(job['company'] is None for job in jobs):
            company = await board_name(token, http, robots)
            for job in jobs:
                job['company'] = job['company'] or company
        for job in jobs:
            if matches(job, settings):
                yield job


async def board_name(token: str, http: PoliteClient, robots: RobotsCache) -> str | None:
    """The company name from the board itself, for the rare job that does not carry it."""
    url = f'{API}/{quote(token)}'
    if not await robots.allowed(url):
        return None
    response = await http.get(url)
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return _text(data.get('name')) if isinstance(data, dict) else None


def parse_jobs(token: str, data: Any) -> list[dict[str, Any]]:
    """The /jobs response as output items. Raises ValueError when it is not a Greenhouse job list."""
    if not isinstance(data, dict) or not isinstance(data.get('jobs'), list):
        raise ValueError('no "jobs" list')
    fetched_at = datetime.now(UTC).isoformat(timespec='seconds')
    return [parse_job(token, job, fetched_at) for job in data['jobs'] if isinstance(job, dict) and job.get('id')]


def parse_job(token: str, job: dict[str, Any], fetched_at: str) -> dict[str, Any]:
    departments = _names(job.get('departments'))
    offices = _names(job.get('offices'))
    location = job.get('location')
    content = job.get('content')
    content_html = html.unescape(content) if isinstance(content, str) and content.strip() else None
    return {
        'board_token': token,
        'company': _text(job.get('company_name')),
        'job_id': job.get('id'),
        'internal_job_id': job.get('internal_job_id'),
        'requisition_id': _text(job.get('requisition_id')),
        'title': _text(job.get('title')),
        'location': _text(location.get('name')) if isinstance(location, dict) else _text(location),
        'department': departments[0] if departments else None,
        'departments': departments,
        'office': offices[0] if offices else None,
        'offices': offices,
        'absolute_url': _text(job.get('absolute_url')),
        'language': _text(job.get('language')),
        'updated_at': _text(job.get('updated_at')),
        'first_published': _text(job.get('first_published')),
        'content': content_html,
        'content_text': html_to_text(content_html) if content_html else None,
        'fetched_at': fetched_at,
    }


def matches(job: dict[str, Any], settings: Settings) -> bool:
    title = (job.get('title') or '').lower()
    location = ' '.join(filter(None, [job.get('location'), *job.get('offices', [])])).lower()
    if settings.title_keywords and not any(k in title for k in settings.title_keywords):
        return False
    return not settings.location_keywords or any(k in location for k in settings.location_keywords)


def html_to_text(markup: str) -> str:
    """The description as plain text, one paragraph or list item per line."""
    soup = BeautifulSoup(markup, 'lxml')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    for block in soup.find_all(_BLOCKS):
        block.insert_before('\n')
        block.append('\n')
    lines = (re.sub(r'\s+', ' ', line).strip() for line in soup.get_text().splitlines())
    return '\n'.join(line for line in lines if line)


def _names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [n for n in (_text(v.get('name')) for v in value if isinstance(v, dict)) if n]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
