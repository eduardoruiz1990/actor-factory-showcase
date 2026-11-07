"""The MCP server AI agents connect to when the Actor runs in Apify's Standby mode.

Three tools: find_job_board (which of the five platforms a company hires through),
search_jobs (its open jobs, filtered) and search_all_companies (by title and
location, without naming companies, through directory.py). With `skills` (for example the skills
an agent read from a CV), search_jobs keeps the jobs whose title or description
mentions at least one and ranks them by how many. Plain company names are resolved by
reading every platform and taking the board with the most open jobs, so an agent
can ask for "notion" without knowing it uses Ashby. The same name can be a
different board elsewhere ("ramp" is one stale job on Greenhouse and about 170 on
Ashby), so the other boards found are reported too. Every job search_jobs returns is also pushed to the run's dataset,
which charges it with Apify's per-item event, exactly as a normal run does; the
user's spending limit stops it the same way.

Apify sends a readiness probe to GET / before a Standby run serves requests, and
forwards MCP requests to /mcp (webServerMcpPath in .actor/actor.json).
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from typing import Any

import uvicorn
from apify import Actor
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from . import directory, privacy, source
from .polite import PoliteClient
from .robots import RobotsCache

MAX_RESULTS = 100  # per call, to keep answers within an agent's context
MAX_SKILLS = 40
MAX_DIRECTORY_BOARDS = 40  # read per search_all_companies call, to keep an agent's wait reasonable
BOARDS_TO_MIX = 5  # search_all_companies reads this many boards, if that many match, so one company can't fill an answer
DESCRIPTION_CHARS = 1500
# Tried in this order for a plain company name.
PLATFORM_PREFIXES = ('', 'lever:', 'ashby:', 'workable:', 'personio:')
_SUMMARY_FIELDS = (
    'title', 'company', 'location', 'department', 'workplace_type', 'employment_type', 'salary_min', 'salary_max',
    'salary_currency', 'salary_interval', 'absolute_url', 'first_published', 'updated_at', 'platform', 'board_token',
    'job_id',
)
INSTRUCTIONS = (
    'Open jobs from company career boards on Greenhouse, Lever, Ashby, Workable and Personio, read from each '
    "platform's public job feed. Give company names (for example 'airbnb' or 'notion') or job board URLs; the server "
    'finds which platform each company uses. To match a CV or a list of skills to open jobs, pass the skills to '
    'search_jobs; it ranks jobs by how many they mention. A name can match boards on several platforms, possibly of '
    'different companies: the board with the most open jobs is used and other_boards lists the rest; pass one '
    "explicitly (for example 'ashby:ramp') to read it. Each job returned is charged as one result."
)


def candidates(company: str) -> list[str]:
    """Board keys to try for one company: an explicit board or URL as given, a plain name on every platform."""
    value = company.strip()
    if ':' in value or '/' in value or '.' in value:
        key = source.board_key(value)
        return [key] if key else []
    names = dict.fromkeys(n for n in (re.sub(r'\s+', '', value), re.sub(r'\s+', '-', value)) if n)
    return [key for name in names for prefix in PLATFORM_PREFIXES if (key := source.board_key(prefix + name))]


async def read_board(key: str, http: PoliteClient, robots: RobotsCache, include_content: bool) -> list[dict[str, Any]]:
    """Every open job on one board, unfiltered (an unknown board logs why and returns none)."""
    settings = source.Settings(board_tokens=[key], max_results=10**6, max_requests_per_second=1.0,
                               include_content=include_content)
    return [job async for job in source.iter_items(settings, http, robots)]


async def resolve(company: str, http: PoliteClient, robots: RobotsCache,
                  include_content: bool = False) -> tuple[str | None, list[dict[str, Any]], dict[str, int]]:
    """The candidate board with the most open jobs (the earlier one on a tie), its jobs, and the other boards found."""
    found: dict[str, list[dict[str, Any]]] = {}
    for key in candidates(company):
        jobs = await read_board(key, http, robots, include_content)
        if jobs:
            found[key] = jobs
    if not found:
        return None, [], {}
    best = max(found, key=lambda key: len(found[key]))
    return best, found[best], {key: len(jobs) for key, jobs in found.items() if key != best}


def matched_skills(job: dict[str, Any], skills: list[str]) -> list[str]:
    """The skills the job's title or description mentions as whole words: "Go" is not "good", nor "C" "C++"."""
    text = ' '.join(filter(None, [job.get('title'), job.get('content_text')]))
    return [s for s in skills if re.search(rf'(?<![\w+#]){re.escape(s)}(?![\w+#])', text, re.IGNORECASE)]


def unique_skills(skills: list[str]) -> list[str]:
    """Each skill once, as first spelled (case aside), at most MAX_SKILLS."""
    unique: dict[str, str] = {}
    for skill in (s.strip() for s in skills):
        if skill:
            unique.setdefault(skill.lower(), skill)
    return list(unique.values())[:MAX_SKILLS]


def summary(job: dict[str, Any], include_description: bool) -> dict[str, Any]:
    result = {field: job.get(field) for field in _SUMMARY_FIELDS}
    if include_description:
        text = job.get('content_text') or ''
        result['description'] = text[:DESCRIPTION_CHARS] + ('…' if len(text) > DESCRIPTION_CHARS else '')
    return result


def build_server(client: Callable[[], PoliteClient] = PoliteClient) -> MCPServer:
    """The MCP server; `client` makes the polite HTTP client for each tool call (tests pass a fake one)."""
    server = MCPServer(name='ats-jobs', title='ATS Jobs', version='0.5', instructions=INSTRUCTIONS)

    @server.custom_route('/', methods=['GET'], include_in_schema=False)
    async def ready(_request: Request) -> PlainTextResponse:
        return PlainTextResponse('ok')  # Apify's readiness probe

    @server.tool(description='Find which job board platform a company uses (Greenhouse, Lever, Ashby, Workable '
                             'or Personio) and how many jobs it has open. If the name matches boards on several '
                             'platforms, the one with the most open jobs is returned and other_boards lists the rest, '
                             'which may belong to a different company. Free: nothing is charged.')
    async def find_job_board(company: str) -> dict[str, Any]:
        async with client() as http:
            key, jobs, others = await resolve(company, http, RobotsCache(http))
        if key is None:
            return {'company': company, 'board': None, 'platform': None, 'open_jobs': 0,
                    'note': 'No open jobs found on Greenhouse, Lever, Ashby, Workable or Personio under this name. '
                            'Try the job board URL from the company careers page.'}
        return ({'company': company, 'board': key, 'platform': jobs[0]['platform'], 'open_jobs': len(jobs)}
                | ({'other_boards': others} if others else {}))

    @server.tool(description='Search the open jobs of one or more companies. Companies are names, board keys '
                             "(such as 'ashby:ramp') or job board URLs; a name uses the board with the most open jobs "
                             'and other_boards lists any others found under it. Optional title and location keywords '
                             '(any match, not case-sensitive). Optional '
                             'skills, such as those listed on a CV: only jobs whose title or description mentions at '
                             'least one are kept, best matches first, each with its matched_skills. Returns up to '
                             f'max_results jobs (at most {MAX_RESULTS}) with salary ranges where published; each job '
                             'returned is charged as one result.')
    async def search_jobs(companies: list[str], title_keywords: list[str] | None = None,
                          location_keywords: list[str] | None = None, skills: list[str] | None = None,
                          max_results: int = 25, include_descriptions: bool = False) -> dict[str, Any]:
        limit = max(1, min(int(max_results), MAX_RESULTS))
        filters = source.Settings(board_tokens=['x'], max_results=limit, max_requests_per_second=1.0,
                                  title_keywords=[k.strip().lower() for k in title_keywords or [] if k.strip()],
                                  location_keywords=[k.strip().lower() for k in location_keywords or [] if k.strip()])
        wanted = unique_skills(skills or [])
        boards: dict[str, str | None] = {}
        other_boards: dict[str, dict[str, int]] = {}
        found_jobs: list[dict[str, Any]] = []
        async with client() as http:
            robots = RobotsCache(http)
            for company in companies[:20]:
                # Skills are matched against descriptions, so those are read whenever skills are given.
                key, found, others = await resolve(company, http, robots,
                                                   include_content=include_descriptions or bool(wanted))
                boards[company] = key
                if others:
                    other_boards[company] = others
                found_jobs.extend(job for job in found if source.matches(job, filters))
                # Without skills the first jobs found are the answer; with skills every company is read to rank them.
                if not wanted and len(found_jobs) >= limit:
                    break
        result = {'boards': boards} | await deliver(found_jobs, wanted, limit, include_descriptions)
        if other_boards:
            result['other_boards'] = other_boards
        return result

    @server.tool(description='Search open jobs across a directory of company job boards by title and location, '
                             'without naming companies. At least one title or location keyword is required (any '
                             'match, not case-sensitive). Optional skills, as in search_jobs. Boards with a matching '
                             'job are read live, the most matches first, and the answer mixes companies. Jobs posted '
                             f'today can be missing until the directory refreshes tomorrow. Reads up to '
                             f'{MAX_DIRECTORY_BOARDS} boards and returns '
                             f'up to max_results jobs (at most {MAX_RESULTS}); each job returned is charged as one '
                             'result.')
    async def search_all_companies(title_keywords: list[str] | None = None, location_keywords: list[str] | None = None,
                                   skills: list[str] | None = None, max_results: int = 25,
                                   include_descriptions: bool = False) -> dict[str, Any]:
        limit = max(1, min(int(max_results), MAX_RESULTS))
        filters = source.Settings(board_tokens=['x'], max_results=limit, max_requests_per_second=1.0,
                                  title_keywords=[k.strip().lower() for k in title_keywords or [] if k.strip()],
                                  location_keywords=[k.strip().lower() for k in location_keywords or [] if k.strip()])
        if not filters.title_keywords and not filters.location_keywords:
            return {'jobs': [], 'charged_results': 0, 'note': 'Give at least one title or location keyword.'}
        wanted = unique_skills(skills or [])
        found_jobs: list[dict[str, Any]] = []
        boards_read = 0
        enough = 0
        per_board = math.ceil(limit / BOARDS_TO_MIX)
        async with client() as http:
            try:
                keys = directory.matching_boards(await directory.load(http), filters)
            except directory.DirectoryUnavailable as exc:
                return {'jobs': [], 'charged_results': 0, 'note': str(exc)}
            robots = RobotsCache(http)
            for key in keys[:MAX_DIRECTORY_BOARDS]:
                jobs = await read_board(key, http, robots, include_descriptions or bool(wanted))
                boards_read += 1
                matching = [job for job in jobs if source.matches(job, filters)]
                found_jobs.extend(matching)
                enough += min(len(matching), per_board)
                if not wanted and enough >= limit:
                    break
        result = {'boards_matched': len(keys), 'boards_read': boards_read}
        return result | await deliver(found_jobs, wanted, limit, include_descriptions, mix_boards=True)

    return server


def take_turns(picked: list[tuple[dict[str, Any], list[str]]], limit: int) -> list[tuple[dict[str, Any], list[str]]]:
    """Up to `limit` jobs: each board's first, then each board's second and so on; the most skills matched come first."""
    turns: dict[tuple[Any, Any], int] = {}
    numbered = []
    for pair in picked:
        board = (pair[0].get('platform'), pair[0].get('board_token'))
        turns[board] = turns.get(board, 0) + 1
        numbered.append((turns[board], pair))
    numbered.sort(key=lambda item: item[0])
    return sorted((pair for _, pair in numbered[:limit]), key=lambda pair: -len(pair[1]))


async def deliver(found_jobs: list[dict[str, Any]], wanted: list[str], limit: int, include_descriptions: bool,
                  mix_boards: bool = False) -> dict[str, Any]:
    """Charge and summarise up to `limit` jobs; with skills, only those mentioning one, the most matches first."""
    picked: list[tuple[dict[str, Any], list[str]]] = [(job, []) for job in found_jobs]
    if wanted:
        ranked = sorted(((job, matched_skills(job, wanted)) for job in found_jobs), key=lambda pair: -len(pair[1]))
        picked = [(job, matched) for job, matched in ranked if matched]
    jobs: list[dict[str, Any]] = []
    stopped = False
    for job, matched in take_turns(picked, limit) if mix_boards else picked[:limit]:
        job = privacy.clean(job)
        if not await _charge(job):
            stopped = True
            break
        jobs.append(summary(job, include_descriptions) | ({'matched_skills': matched} if wanted else {}))
    result: dict[str, Any] = {'jobs': jobs, 'charged_results': len(jobs)}
    if stopped:
        result['note'] = 'Stopped: the spending limit of this Actor run is used up.'
    return result


async def _charge(job: dict[str, Any]) -> bool:
    """Push the job to the run's dataset, which charges it; False once the user's spending limit is used up."""
    result = await Actor.push_data(job)
    pricing = Actor.get_charging_manager().get_pricing_info()
    return not (pricing.is_pay_per_event and result.charged_count == 0)


async def serve() -> None:
    """Run the MCP server on the port Apify gives a Standby run, until the run ends."""
    app = build_server().streamable_http_app(
        streamable_http_path='/mcp', stateless_http=True, json_response=True,
        # Requests reach the server through Apify's public Standby URL, so the default localhost-only host
        # check would reject every one of them; Apify's proxy is the only way in.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    config = uvicorn.Config(app, host='0.0.0.0', port=Actor.configuration.web_server_port, log_level='info')
    await uvicorn.Server(config).serve()
