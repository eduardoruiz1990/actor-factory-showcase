"""The MCP server AI agents connect to when the Actor runs in Apify's Standby mode.

Two tools: find_job_board (which of the five platforms a company hires through)
and search_jobs (its open jobs, filtered). Plain company names are resolved by
trying each platform in turn, so an agent can ask for "notion" without knowing
it uses Ashby. Every job search_jobs returns is also pushed to the run's dataset,
which charges it with Apify's per-item event, exactly as a normal run does; the
user's spending limit stops it the same way.

Apify sends a readiness probe to GET / before a Standby run serves requests, and
forwards MCP requests to /mcp (webServerMcpPath in .actor/actor.json).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import uvicorn
from apify import Actor
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from . import privacy, source
from .polite import PoliteClient
from .robots import RobotsCache

MAX_RESULTS = 100  # per call, to keep answers within an agent's context
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
    'finds which platform each company uses. Each job returned is charged as one result.'
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
                  include_content: bool = False) -> tuple[str | None, list[dict[str, Any]]]:
    """The first candidate board with open jobs, and those jobs."""
    for key in candidates(company):
        jobs = await read_board(key, http, robots, include_content)
        if jobs:
            return key, jobs
    return None, []


def summary(job: dict[str, Any], include_description: bool) -> dict[str, Any]:
    result = {field: job.get(field) for field in _SUMMARY_FIELDS}
    if include_description:
        text = job.get('content_text') or ''
        result['description'] = text[:DESCRIPTION_CHARS] + ('…' if len(text) > DESCRIPTION_CHARS else '')
    return result


def build_server(client: Callable[[], PoliteClient] = PoliteClient) -> MCPServer:
    """The MCP server; `client` makes the polite HTTP client for each tool call (tests pass a fake one)."""
    server = MCPServer(name='ats-jobs', title='ATS Jobs', version='0.1', instructions=INSTRUCTIONS)

    @server.custom_route('/', methods=['GET'], include_in_schema=False)
    async def ready(_request: Request) -> PlainTextResponse:
        return PlainTextResponse('ok')  # Apify's readiness probe

    @server.tool(description='Find which job board platform a company uses (Greenhouse, Lever, Ashby, Workable '
                             'or Personio) and how many jobs it has open. Free: nothing is charged.')
    async def find_job_board(company: str) -> dict[str, Any]:
        async with client() as http:
            key, jobs = await resolve(company, http, RobotsCache(http))
        if key is None:
            return {'company': company, 'board': None, 'platform': None, 'open_jobs': 0,
                    'note': 'No open jobs found on Greenhouse, Lever, Ashby, Workable or Personio under this name. '
                            'Try the job board URL from the company careers page.'}
        return {'company': company, 'board': key, 'platform': jobs[0]['platform'], 'open_jobs': len(jobs)}

    @server.tool(description='Search the open jobs of one or more companies. Companies are names or job board '
                             'URLs. Optional title and location keywords (any match, not case-sensitive). Returns '
                             f'up to max_results jobs (at most {MAX_RESULTS}) with salary ranges where published; '
                             'each job returned is charged as one result.')
    async def search_jobs(companies: list[str], title_keywords: list[str] | None = None,
                          location_keywords: list[str] | None = None, max_results: int = 25,
                          include_descriptions: bool = False) -> dict[str, Any]:
        limit = max(1, min(int(max_results), MAX_RESULTS))
        filters = source.Settings(board_tokens=['x'], max_results=limit, max_requests_per_second=1.0,
                                  title_keywords=[k.strip().lower() for k in title_keywords or [] if k.strip()],
                                  location_keywords=[k.strip().lower() for k in location_keywords or [] if k.strip()])
        boards: dict[str, str | None] = {}
        jobs: list[dict[str, Any]] = []
        stopped = False
        async with client() as http:
            robots = RobotsCache(http)
            for company in companies[:20]:
                key, found = await resolve(company, http, robots, include_content=include_descriptions)
                boards[company] = key
                for job in found:
                    if len(jobs) >= limit:
                        break
                    if not source.matches(job, filters):
                        continue
                    job = privacy.clean(job)
                    if not await _charge(job):
                        stopped = True
                        break
                    jobs.append(summary(job, include_descriptions))
                if stopped or len(jobs) >= limit:
                    break
        result: dict[str, Any] = {'boards': boards, 'jobs': jobs, 'charged_results': len(jobs)}
        if stopped:
            result['note'] = 'Stopped: the spending limit of this Actor run is used up.'
        return result

    return server


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
