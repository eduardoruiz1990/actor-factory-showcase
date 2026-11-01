"""Company job boards on Greenhouse, Lever, Ashby, Workable and Personio: every open job, from each platform's public feed.

One request per board:
- Greenhouse: GET boards-api.greenhouse.io/v1/boards/<token>/jobs?content=true&pay_transparency=true
- Lever: GET api.lever.co/v0/postings/<site>?mode=json (api.eu.lever.co for EU-hosted boards)
- Ashby: GET api.ashbyhq.com/posting-api/job-board/<name>?includeCompensation=true
- Workable: GET apply.workable.com/api/v1/widget/accounts/<account>?details=true (where Workable's documented
  public endpoint www.workable.com/api/accounts/<account>?details=true redirects)
- Personio: GET <company>.jobs.personio.com/xml, the documented XML job feed
The feeds are public and need no key; Lever's documentation says published postings
"may be scraped by third parties". Ashby's, Workable's and Personio's documentation does not
address third-party use; the owner reviewed that and approved them (QUESTIONS Q19, Q21). Every URL is still checked against
the API host's robots.txt before it is fetched (Ashby's answers 401, which RFC 9309 reads as
"no robots.txt"). Keep the contract: iter_items() yields plain dicts and fetches only through `http`.

A board is a key in Settings.board_tokens: a plain token is a Greenhouse board ("airbnb"),
"lever:<site>" and "lever-eu:<site>" are Lever boards, "ashby:<name>", "workable:<account>" and
"personio:<company>" boards on those platforms.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlsplit

from apify import Actor
from bs4 import BeautifulSoup

from .polite import PoliteClient
from .robots import RobotsCache
from .seen import state_key

API = 'https://boards-api.greenhouse.io/v1/boards'
# Lever's robots.txt asks for a 1-second crawl delay; one rate for every host keeps the rule simple.
MAX_RATE = 1.0
LEVER_API = {'lever': 'https://api.lever.co/v0/postings', 'lever-eu': 'https://api.eu.lever.co/v0/postings'}
ASHBY_API = 'https://api.ashbyhq.com/posting-api/job-board'
WORKABLE_API = 'https://apply.workable.com/api/v1/widget/accounts'
PERSONIO_HOST = 'jobs.personio.com'  # jobs.personio.de serves the same feeds
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
    only_new: bool = False
    report_removed: bool = False
    state_key: str = ''  # which earlier runs count as "the same search" for only_new and report_removed

    @classmethod
    def from_input(cls, actor_input: dict[str, Any]) -> Settings:
        tokens: list[str] = []
        for raw in _board_entries(actor_input.get('boardTokens')):
            token = board_key(raw)
            if token is None:
                Actor.log.warning(f'{raw!r} is not a Greenhouse, Lever, Ashby, Workable or Personio board token or URL; skipped')
            elif token not in tokens:
                tokens.append(token)
        if not tokens:
            raise ValueError('Input needs at least one board in "boardTokens" (for example "airbnb", "lever:palantir" or "ashby:ramp").')
        max_results = int(actor_input.get('maxResults') or 1000)
        rate = float(actor_input.get('maxRequestsPerSecond') or 1)
        title_keywords = _keywords(actor_input.get('titleKeywords'))
        location_keywords = _keywords(actor_input.get('locationKeywords'))
        # Runs with the same monitor name, or else the same boards and filters, share one memory of returned jobs.
        identity = (actor_input.get('monitorName') or '').strip() or {
            'boards': sorted(tokens), 'titles': sorted(title_keywords), 'locations': sorted(location_keywords)}
        return cls(
            board_tokens=tokens,
            max_results=max(1, max_results),
            max_requests_per_second=min(max(rate, 0.1), MAX_RATE),
            include_content=actor_input.get('includeContent', True) is not False,
            title_keywords=title_keywords,
            location_keywords=location_keywords,
            only_new=actor_input.get('onlyNew') is True,
            report_removed=actor_input.get('reportRemoved') is True,
            state_key=state_key(identity),
        )


def item_key(item: dict[str, Any]) -> str:
    """The same job in every run gets the same key: platform, board and the platform's job ID."""
    return f"{item['platform']}:{item['board_token']}:{item['job_id']}"


def board_of(key: str) -> str:
    """An input board ('airbnb', 'lever-eu:zoox') named as its jobs' keys start: '<platform>:<board_token>'."""
    platform, _, site = key.rpartition(':')
    return f"{'lever' if platform in LEVER_API else platform or 'greenhouse'}:{site}"


def _board_entries(value: Any) -> list[Any]:
    """Boards typed several to a line ('airbnb, lever:zoox') are split on commas, semicolons and line breaks.

    Not on spaces: 'Acme Corp' must stay one (invalid) entry, not become the boards 'acme' and 'corp'.
    """
    if isinstance(value, str | dict):
        value = [value]
    if not isinstance(value, list):
        return []
    entries: list[Any] = []
    for raw in value:
        raw = raw.get('url') if isinstance(raw, dict) else raw
        if isinstance(raw, str):
            entries += [part for part in re.split(r'[,;\n]+', raw) if part]
        else:
            entries.append(raw)
    return entries


def board_key(value: Any) -> str | None:
    """A board as Settings keeps it: 'airbnb' (Greenhouse), 'lever:palantir' or 'lever-eu:acme' (Lever)."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    prefix, _, rest = value.partition(':')
    prefix = prefix.lower()
    if prefix == 'greenhouse' and not rest.startswith('//'):
        return board_token(rest)
    if (prefix in LEVER_API or prefix in ('ashby', 'workable', 'personio')) and not rest.startswith('//'):
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
        if host in ('jobs.ashbyhq.com', 'api.ashbyhq.com'):
            path = [p for p in parts.path.split('/') if p]
            if path[:2] == ['posting-api', 'job-board']:
                path = path[2:]
            name = path[0].lower() if path else ''  # Ashby board names are not case-sensitive
            return f'ashby:{name}' if _TOKEN.match(name) else None
        if host in ('apply.workable.com', 'www.workable.com') or (host.endswith('.workable.com') and host != 'workable.com'):
            path = [p for p in parts.path.split('/') if p]
            for prefix_path in (['api', 'v1', 'widget', 'accounts'], ['api', 'accounts']):
                if path[:len(prefix_path)] == prefix_path:
                    path = path[len(prefix_path):]
            if host not in ('apply.workable.com', 'www.workable.com'):
                path = [host.split('.')[0]]  # <account>.workable.com
            name = path[0].lower() if path and path[0] != 'j' else ''  # /j/<code> links do not name the account
            return f'workable:{name}' if _TOKEN.match(name) else None
        for personio in ('.jobs.personio.com', '.jobs.personio.de'):
            if host.endswith(personio):
                name = host[: -len(personio)]
                return f'personio:{name}' if _TOKEN.match(name) and '.' not in name else None
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


async def iter_items(
    settings: Settings, http: PoliteClient, robots: RobotsCache, read: set[str] | None = None
) -> AsyncIterator[dict[str, Any]]:
    """Every matching job; `read` collects the boards that answered (board_of), so a failed board's jobs are not gone."""
    for key in settings.board_tokens:
        platform, _, site = key.rpartition(':')
        if platform in LEVER_API:
            jobs = await _fetch(f'{LEVER_API[platform]}/{quote(site)}?mode=json', 'Lever', site, http, robots,
                                lambda data: parse_lever_jobs(site, data, settings.include_content))
        elif platform == 'ashby':
            jobs = await _fetch(f'{ASHBY_API}/{quote(site)}?includeCompensation=true', 'Ashby', site, http, robots,
                                lambda data: parse_ashby_jobs(site, data, settings.include_content))
        elif platform == 'workable':
            jobs = await _fetch(f'{WORKABLE_API}/{quote(site)}?details=true', 'Workable', site, http, robots,
                                lambda data: parse_workable_jobs(site, data, settings.include_content))
        elif platform == 'personio':
            jobs = await _fetch(f'https://{site}.{PERSONIO_HOST}/xml', 'Personio', site, http, robots,
                                lambda text: parse_personio_jobs(site, text, settings.include_content), text=True)
        else:
            url = f'{API}/{quote(key)}/jobs?' + ('content=true&' if settings.include_content else '') + 'pay_transparency=true'
            jobs = await _fetch(url, 'Greenhouse', key, http, robots, lambda data: parse_jobs(key, data))
            if jobs and any(job['company'] is None for job in jobs):
                company = await board_name(key, http, robots)
                for job in jobs:
                    job['company'] = job['company'] or company
        if jobs is not None and read is not None:
            read.add(board_of(key))
        for job in jobs or []:
            if matches(job, settings):
                yield job


async def _fetch(
    url: str, platform: str, name: str, http: PoliteClient, robots: RobotsCache, parse: Any, text: bool = False
) -> list[dict[str, Any]] | None:
    """One board's jobs, or None (with a log line) when the board is disallowed, unknown or unreadable.

    `parse` gets the decoded JSON, or the response text when `text` is set (Personio's XML feed).
    """
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
        jobs = parse(response.text if text else response.json())
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
        'employment_type': None,
        'workplace_type': None,
        **_greenhouse_salary(job.get('pay_input_ranges')),
        'fetched_at': fetched_at,
    }


# Greenhouse names each pay range freely ("Pay Range", "Mexico Monthly Pay Range"); the interval is read from that
# name in Lever's words, and left null when the name does not say.
_INTERVALS = [('hour', 'per-hour-wage'), ('dai', 'per-day-wage'), ('day', 'per-day-wage'),
              ('month', 'per-month-salary'), ('annual', 'per-year-salary'), ('year', 'per-year-salary')]


def _greenhouse_salary(ranges: Any) -> dict[str, Any]:
    """The job's first pay range (a job may list one per country), from the board's pay transparency data."""
    first = ranges[0] if isinstance(ranges, list) and ranges and isinstance(ranges[0], dict) else {}
    title = str(first.get('title') or '').lower()
    return {
        'salary_min': _from_cents(first.get('min_cents')),
        'salary_max': _from_cents(first.get('max_cents')),
        'salary_currency': _text(first.get('currency_type')),
        'salary_interval': next((interval for word, interval in _INTERVALS if word in title), None),
    }


def _from_cents(value: Any) -> int | float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return value // 100 if isinstance(value, int) and value % 100 == 0 else value / 100


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


def parse_ashby_jobs(name: str, data: Any, include_content: bool = True) -> list[dict[str, Any]]:
    """The Ashby job board response as output items. Raises ValueError when it is not one.

    Jobs marked isListed=false are left out: Ashby says they "should only be available via direct link".
    """
    if not isinstance(data, dict) or not isinstance(data.get('jobs'), list):
        raise ValueError('no "jobs" list')
    fetched_at = datetime.now(UTC).isoformat(timespec='seconds')
    return [parse_ashby_job(name, job, fetched_at, include_content) for job in data['jobs']
            if isinstance(job, dict) and job.get('id') and job.get('isListed', True) is not False]


_ASHBY_EMPLOYMENT = {'FullTime': 'Full-time', 'PartTime': 'Part-time', 'Intern': 'Intern', 'Contract': 'Contract',
                     'Temporary': 'Temporary'}
_ASHBY_INTERVALS = {'1 YEAR': 'per-year-salary', '1 MONTH': 'per-month-salary', '1 WEEK': 'per-week-salary',
                    '1 DAY': 'per-day-wage', '1 HOUR': 'per-hour-wage'}


def parse_ashby_job(name: str, job: dict[str, Any], fetched_at: str, include_content: bool = True) -> dict[str, Any]:
    location = _text(job.get('location'))
    secondary = [_text(s.get('location')) for s in job.get('secondaryLocations') or [] if isinstance(s, dict)]
    offices = list(dict.fromkeys(t for t in (location, *secondary) if t))
    departments = list(dict.fromkeys(t for t in (_text(job.get('department')), _text(job.get('team'))) if t))
    content = job.get('descriptionHtml')
    content_html = content if include_content and isinstance(content, str) and content.strip() else None
    workplace = _text(job.get('workplaceType'))
    return {
        'platform': 'ashby',
        'board_token': name,
        'company': None,  # Ashby's public API does not publish the company's display name
        'job_id': _text(job.get('id')),
        'internal_job_id': None,
        'requisition_id': None,
        'title': _text(job.get('title')),
        'location': location,
        'department': departments[0] if departments else None,
        'departments': departments,
        'office': location,
        'offices': offices,
        'absolute_url': _text(job.get('jobUrl')),
        'language': None,
        'updated_at': _text(job.get('publishedAt')),  # Ashby: "when the job was last published"
        'first_published': None,
        'content': content_html,
        'content_text': html_to_text(content_html) if content_html else None,
        'employment_type': _ASHBY_EMPLOYMENT.get(job.get('employmentType'), _text(job.get('employmentType'))),
        'workplace_type': workplace.lower() if workplace else None,
        **_ashby_salary(job),
        'fetched_at': fetched_at,
    }


def _ashby_salary(job: dict[str, Any]) -> dict[str, Any]:
    """The salary range from Ashby's compensation summary, only when the company shows pay on its job posting."""
    salary: dict[str, Any] = {}
    compensation = job.get('compensation') if isinstance(job.get('compensation'), dict) else {}
    if job.get('shouldDisplayCompensationOnJobPostings') is True:
        salary = next((c for c in compensation.get('summaryComponents') or []
                       if isinstance(c, dict) and c.get('compensationType') == 'Salary'), {})
    return {
        'salary_min': _number(salary.get('minValue')),
        'salary_max': _number(salary.get('maxValue')),
        'salary_currency': _text(salary.get('currencyCode')),
        'salary_interval': _ASHBY_INTERVALS.get(salary.get('interval')) if salary else None,
    }


def parse_workable_jobs(account: str, data: Any, include_content: bool = True) -> list[dict[str, Any]]:
    """The Workable widget response (company name plus its published jobs) as output items. Raises ValueError otherwise."""
    if not isinstance(data, dict) or not isinstance(data.get('jobs'), list):
        raise ValueError('no "jobs" list')
    fetched_at = datetime.now(UTC).isoformat(timespec='seconds')
    company = _text(data.get('name'))
    return [parse_workable_job(account, company, job, fetched_at, include_content)
            for job in data['jobs'] if isinstance(job, dict) and job.get('shortcode')]


def parse_workable_job(
    account: str, company: str | None, job: dict[str, Any], fetched_at: str, include_content: bool = True
) -> dict[str, Any]:
    places = [loc for loc in job.get('locations') or [] if isinstance(loc, dict) and not loc.get('hidden')]
    offices = list(dict.fromkeys(t for t in (_place(loc.get('city'), loc.get('region'), loc.get('country'))
                                             for loc in places) if t))
    location = _place(job.get('city'), job.get('state'), job.get('country')) or (offices[0] if offices else None)
    department = _text(job.get('department'))
    content = job.get('description')
    content_html = content if include_content and isinstance(content, str) and content.strip() else None
    return {
        'platform': 'workable',
        'board_token': account,
        'company': company,
        'job_id': _text(job.get('shortcode')),
        'internal_job_id': None,
        'requisition_id': _text(job.get('code')),
        'title': _text(job.get('title')),
        'location': location,
        'department': department,
        'departments': [department] if department else [],
        'office': location,
        'offices': offices or ([location] if location else []),
        'absolute_url': _text(job.get('url')),
        'language': None,
        'updated_at': None,
        'first_published': _text(job.get('published_on')),  # a date, without a time
        'content': content_html,
        'content_text': html_to_text(content_html) if content_html else None,
        'employment_type': _text(job.get('employment_type')),
        'workplace_type': 'remote' if job.get('telecommuting') is True else None,
        'salary_min': None, 'salary_max': None, 'salary_currency': None, 'salary_interval': None,
        'fetched_at': fetched_at,
    }


def _place(*parts: Any) -> str | None:
    return ', '.join(dict.fromkeys(t for t in (_text(p) for p in parts) if t)) or None


_PERSONIO_SCHEDULE = {'full-time': 'Full-time', 'part-time': 'Part-time', 'full-or-part-time': 'Full-time or part-time'}
_PERSONIO_INTERVALS = {'yearly': 'per-year-salary', 'monthly': 'per-month-salary', 'weekly': 'per-week-salary',
                       'daily': 'per-day-wage', 'hourly': 'per-hour-wage'}


def parse_personio_jobs(company: str, text: Any, include_content: bool = True) -> list[dict[str, Any]]:
    """Personio's XML feed (<workzag-jobs><position>...) as output items. Raises ValueError when it is not one."""
    if not isinstance(text, str):
        raise ValueError('not an XML document')
    try:
        root = ET.fromstring(text)  # ElementTree resolves no external entities
    except ET.ParseError as exc:
        raise ValueError(f'not XML ({exc})') from exc
    if root.tag != 'workzag-jobs':
        raise ValueError(f'unexpected XML root <{root.tag}>')
    fetched_at = datetime.now(UTC).isoformat(timespec='seconds')
    return [parse_personio_job(company, position, fetched_at, include_content)
            for position in root.findall('position') if _text(position.findtext('id'))]


def parse_personio_job(company: str, position: ET.Element, fetched_at: str, include_content: bool = True) -> dict[str, Any]:
    job_id = _text(position.findtext('id'))
    office = _text(position.findtext('office'))
    offices = list(dict.fromkeys(t for t in (office, *(_text(o.text) for o in position.findall('additionalOffices/office'))) if t))
    department = _text(position.findtext('department'))
    content_html = None
    if include_content:
        sections = [(_text(d.findtext('name')), d.findtext('value') or '') for d in position.findall('jobDescriptions/jobDescription')]
        content_html = ''.join(f'<h3>{html.escape(name)}</h3>{value}' if name else value
                               for name, value in sections if value.strip()) or None
    salary = position.find('salaryInformation')
    schedule = _text(position.findtext('schedule'))
    employment = _text(position.findtext('employmentType'))
    return {
        'platform': 'personio',
        'board_token': company,
        'company': _text(position.findtext('subcompany')),
        'job_id': int(job_id) if job_id and job_id.isdigit() else job_id,
        'internal_job_id': None,
        'requisition_id': None,
        'title': _text(position.findtext('name')),
        'location': office,
        'department': department,
        'departments': [department] if department else [],
        'office': office,
        'offices': offices,
        'absolute_url': f'https://{company}.{PERSONIO_HOST}/job/{quote(job_id)}' if job_id else None,
        'language': None,
        'updated_at': None,
        'first_published': _text(position.findtext('createdAt')),
        'content': content_html,
        'content_text': html_to_text(content_html) if content_html else None,
        'employment_type': _PERSONIO_SCHEDULE.get(schedule or '') or (employment.replace('_', ' ').capitalize() if employment else None),
        'workplace_type': None,
        'salary_min': _decimal(salary.findtext('min')) if salary is not None else None,
        'salary_max': _decimal(salary.findtext('max')) if salary is not None else None,
        'salary_currency': _text(salary.findtext('currencyCode')) if salary is not None else None,
        'salary_interval': _PERSONIO_INTERVALS.get(salary.findtext('type') or '') if salary is not None else None,
        'fetched_at': fetched_at,
    }


def _decimal(value: Any) -> int | float | None:
    """'80000.00' -> 80000; anything that is not a number -> None."""
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _number(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


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
