"""Company job boards on Greenhouse and Lever: every open job, read from each platform's official public API.

One request per board:
- Greenhouse: GET boards-api.greenhouse.io/v1/boards/<token>/jobs?content=true
- Lever: GET api.lever.co/v0/postings/<site>?mode=json (api.eu.lever.co for EU-hosted boards)
Both APIs are public and need no key; Lever's documentation says published postings
"may be scraped by third parties". Every URL is still checked against the API host's
robots.txt before it is fetched. Keep the contract: iter_items() yields plain dicts and
fetches only through `http`.

A board is a key in Settings.board_tokens: a plain token is a Greenhouse board ("airbnb"),
"lever:<site>" and "lever-eu:<site>" are Lever boards.
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
# Lever's robots.txt asks for a 1-second crawl delay; one rate for every host keeps the rule simple.
MAX_RATE = 1.0
LEVER_API = {'lever': 'https://api.lever.co/v0/postings', 'lever-eu': 'https://api.eu.lever.co/v0/postings'}
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
            token = board_key(raw.get('url') if isinstance(raw, dict) else raw)
            if token is None:
                Actor.log.warning(f'{raw!r} is not a Greenhouse or Lever board token or URL; skipped')
            elif token not in tokens:
                tokens.append(token)
        if not tokens:
            raise ValueError('Input needs at least one board in "boardTokens" (for example "airbnb" or "lever:palantir").')
        max_results = int(actor_input.get('maxResults') or 1000)
        rate = float(actor_input.get('maxRequestsPerSecond') or 1)
        return cls(
            board_tokens=tokens,
            max_results=max(1, max_results),
            max_requests_per_second=min(max(rate, 0.1), MAX_RATE),
            include_content=actor_input.get('includeContent', True) is not False,
            title_keywords=_keywords(actor_input.get('titleKeywords')),
            location_keywords=_keywords(actor_input.get('locationKeywords')),
        )


def board_key(value: Any) -> str | None:
    """A board as Settings keeps it: 'airbnb' (Greenhouse), 'lever:palantir' or 'lever-eu:acme' (Lever)."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    prefix, _, rest = value.partition(':')
    prefix = prefix.lower()
    if prefix == 'greenhouse' and not rest.startswith('//'):
        return board_token(rest)
    if prefix in LEVER_API and not rest.startswith('//'):
        site = rest.strip().lower()
        return f'{prefix}:{site}' if _TOKEN.match(site) else None
    if '/' in value or '.' in value:
        parts = urlsplit(value if '://' in value else f'https://{value}')
        host = (parts.hostname or '').lower()
        lever = {'jobs.lever.co': 'lever', 'api.lever.co': 'lever', 'jobs.eu.lever.co': 'lever-eu',
                 'api.eu.lever.co': 'lever-eu'}.get(host)
        if lever:
            path = [p for p in parts.path.split('/') if p]
            if path[:2] == ['v0', 'postings']:
                path = path[2:]
            site = path[0].lower() if path else ''
            return f'{lever}:{site}' if _TOKEN.match(site) else None
    return board_token(value)


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
    for key in settings.board_tokens:
        platform, _, site = key.rpartition(':')
        if platform in LEVER_API:
            jobs = await _fetch(f'{LEVER_API[platform]}/{quote(site)}?mode=json', 'Lever', site, http, robots,
                                lambda data: parse_lever_jobs(site, data, settings.include_content))
        else:
            url = f'{API}/{quote(key)}/jobs' + ('?content=true' if settings.include_content else '')
            jobs = await _fetch(url, 'Greenhouse', key, http, robots, lambda data: parse_jobs(key, data))
            if jobs and any(job['company'] is None for job in jobs):
                company = await board_name(key, http, robots)
                for job in jobs:
                    job['company'] = job['company'] or company
        for job in jobs or []:
            if matches(job, settings):
                yield job


async def _fetch(
    url: str, platform: str, name: str, http: PoliteClient, robots: RobotsCache, parse: Any
) -> list[dict[str, Any]] | None:
    """One board's jobs, or None (with a log line) when the board is disallowed, unknown or unreadable."""
    if not await robots.allowed(url):
        Actor.log.warning(f'robots.txt does not allow {url}; skipped')
        return None
    response = await http.get(url)
    if response.status_code == 404:
        Actor.log.warning(f'No {platform} board called "{name}" (HTTP 404); skipped')
        return None
    if response.status_code != 200:
        Actor.log.warning(f'{platform} board "{name}" returned HTTP {response.status_code}; skipped')
        return None
    try:
        jobs = parse(response.json())
    except ValueError as exc:
        Actor.log.warning(f'{platform} board "{name}" sent a response that could not be read ({exc}); skipped')
        return None
    Actor.log.info(f'{platform} board "{name}": {len(jobs)} open job(s)')
    return jobs


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
        'platform': 'greenhouse',
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
        **_NO_LEVER_FIELDS,
        'fetched_at': fetched_at,
    }


# Fields only Lever publishes; Greenhouse items carry them as null so every item has the same shape.
_NO_LEVER_FIELDS: dict[str, Any] = {
    'employment_type': None, 'workplace_type': None,
    'salary_min': None, 'salary_max': None, 'salary_currency': None, 'salary_interval': None,
}


def parse_lever_jobs(site: str, data: Any, include_content: bool = True) -> list[dict[str, Any]]:
    """The Lever postings response (a JSON list) as output items. Raises ValueError for anything else."""
    if not isinstance(data, list):
        raise ValueError('not a list of postings')
    fetched_at = datetime.now(UTC).isoformat(timespec='seconds')
    return [parse_lever_job(site, posting, fetched_at, include_content)
            for posting in data if isinstance(posting, dict) and posting.get('id')]


def parse_lever_job(site: str, posting: dict[str, Any], fetched_at: str, include_content: bool = True) -> dict[str, Any]:
    categories = posting.get('categories') if isinstance(posting.get('categories'), dict) else {}
    location = _text(categories.get('location'))
    locations = [t for t in (_text(v) for v in categories.get('allLocations') or [] if isinstance(v, str)) if t]
    departments = list(dict.fromkeys(t for t in (_text(categories.get('department')), _text(categories.get('team'))) if t))
    salary = posting.get('salaryRange') if isinstance(posting.get('salaryRange'), dict) else {}
    content_html = _lever_html(posting) if include_content else None
    created = posting.get('createdAt')
    return {
        'platform': 'lever',
        'board_token': site,
        'company': None,  # Lever's public API does not publish the company's display name
        'job_id': _text(posting.get('id')),
        'internal_job_id': None,
        'requisition_id': None,
        'title': _text(posting.get('text')),
        'location': location,
        'department': departments[0] if departments else None,
        'departments': departments,
        'office': location,
        'offices': locations or ([location] if location else []),
        'absolute_url': _text(posting.get('hostedUrl')),
        'language': None,
        'updated_at': None,
        'first_published': _iso_from_ms(created),
        'content': content_html,
        'content_text': html_to_text(content_html) if content_html else None,
        'employment_type': _text(categories.get('commitment')),
        'workplace_type': _text(posting.get('workplaceType')),
        'salary_min': salary.get('min') if isinstance(salary.get('min'), (int, float)) else None,
        'salary_max': salary.get('max') if isinstance(salary.get('max'), (int, float)) else None,
        'salary_currency': _text(salary.get('currency')),
        'salary_interval': _text(salary.get('interval')),
        'fetched_at': fetched_at,
    }


def _lever_html(posting: dict[str, Any]) -> str | None:
    """The full posting as one HTML document: description, each list section, then the closing text."""
    parts = [posting.get('description')]
    for section in posting.get('lists') or []:
        if isinstance(section, dict):
            parts.append(f"<h3>{html.escape(str(section.get('text') or ''))}</h3><ul>{section.get('content') or ''}</ul>")
    parts += [posting.get('salaryDescription'), posting.get('additional')]
    joined = ''.join(p for p in parts if isinstance(p, str) and p.strip())
    return joined or None


def _iso_from_ms(value: Any) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, UTC).isoformat(timespec='seconds')


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
