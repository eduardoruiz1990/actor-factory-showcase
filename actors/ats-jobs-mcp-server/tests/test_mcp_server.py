"""The MCP server: company resolution, both tools, charging, and the HTTP app Apify's Standby mode talks to."""

import asyncio
import json
from pathlib import Path

import httpx2
import pytest
from starlette.testclient import TestClient

from my_actor import mcp_server
from my_actor.mcp_server import build_server, candidates
from my_actor.polite import PoliteClient

FIXTURES = Path(__file__).parent / 'fixtures'
WARP = json.loads((FIXTURES / 'ashby_warp.json').read_text())
ZOOX = json.loads((FIXTURES / 'lever_zoox.json').read_text())
ALLOW = httpx2.Response(200, text='User-agent: *\nAllow: /\n')


def fake_client(routes, seen):
    """A polite client against fake platform APIs; `routes` maps 'host/path?query' to a response."""

    def handler(request):
        target = f'{request.url.host}{request.url.path}' + (f'?{request.url.query.decode()}' if request.url.query else '')
        seen.append(target)
        if request.url.path == '/robots.txt':
            return routes.get(target, ALLOW)
        return routes.get(target, httpx2.Response(404, json={'error': 'Not Found'}))

    async def no_sleep(_):
        return None

    return lambda: PoliteClient(min_interval=0, max_retries=0, transport=httpx2.MockTransport(handler), sleep=no_sleep)


ROUTES = {
    'api.ashbyhq.com/robots.txt': httpx2.Response(401),  # RFC 9309: no robots.txt (Q19)
    'api.ashbyhq.com/posting-api/job-board/warp?includeCompensation=true': httpx2.Response(200, json=WARP),
    'api.lever.co/v0/postings/zoox?mode=json': httpx2.Response(200, json=ZOOX),
}


class Charges(list):
    """What search_jobs pushed (and so charged); pushes past `limit` report the spending limit as used up."""

    limit = float('inf')

    async def charge(self, job):
        self.append(job)
        return len(self) <= self.limit


@pytest.fixture
def charged(monkeypatch):
    charges = Charges()
    monkeypatch.setattr(mcp_server, '_charge', charges.charge)
    return charges


def call(server, tool, **arguments):
    result = asyncio.run(server.call_tool(tool, arguments))
    assert not result.is_error, result.content
    return result.structured_content


def test_candidates_try_every_platform_for_a_plain_name():
    assert candidates('Warp') == ['warp', 'lever:warp', 'ashby:warp', 'workable:warp', 'personio:warp']
    assert candidates('Hugging Face')[:2] == ['huggingface', 'lever:huggingface']
    assert 'ashby:hugging-face' in candidates('Hugging Face')
    assert candidates('https://jobs.ashbyhq.com/Ramp') == ['ashby:ramp']
    assert candidates('https://example.com/careers') == []


def test_find_job_board_resolves_a_company_on_its_platform_for_free(charged):
    seen = []
    server = build_server(fake_client(ROUTES, seen))
    found = call(server, 'find_job_board', company='Warp')
    assert found == {'company': 'Warp', 'board': 'ashby:warp', 'platform': 'ashby', 'open_jobs': 3}
    # Greenhouse and Lever were asked first and answered 404; nothing was charged.
    assert 'boards-api.greenhouse.io/v1/boards/warp/jobs?pay_transparency=true' in seen and charged == []
    missing = call(server, 'find_job_board', company='nobody-here')
    assert missing['board'] is None and missing['open_jobs'] == 0


def test_search_jobs_filters_charges_each_job_and_returns_a_compact_summary(charged):
    server = build_server(fake_client(ROUTES, []))
    found = call(server, 'search_jobs', companies=['warp', 'https://jobs.lever.co/zoox'], title_keywords=['account'])
    assert found['boards'] == {'warp': 'ashby:warp', 'https://jobs.lever.co/zoox': 'lever:zoox'}
    assert [j['title'] for j in found['jobs']] == ['Account Executive']
    job = found['jobs'][0]
    assert (job['salary_min'], job['salary_max'], job['platform']) == (160000, 200000, 'ashby')
    assert 'description' not in job and found['charged_results'] == 1
    assert len(charged) == 1 and charged[0]['content'] is None  # the full job went to the dataset


def test_search_jobs_caps_results_and_can_include_short_descriptions(charged):
    server = build_server(fake_client(ROUTES, []))
    found = call(server, 'search_jobs', companies=['warp'], max_results=1, include_descriptions=True)
    assert len(found['jobs']) == 1 and len(charged) == 1
    assert 0 < len(found['jobs'][0]['description']) <= mcp_server.DESCRIPTION_CHARS + 1


def test_search_jobs_ranks_jobs_by_the_skills_they_mention(charged):
    server = build_server(fake_client(ROUTES, []))
    found = call(server, 'search_jobs', companies=['zoox', 'warp'], skills=['Salesforce', 'LLM', 'Rust', ' llm '])
    titles = [j['title'] for j in found['jobs']]
    # Zoox was read first but mentions none of them; Warp's Account Executive mentions two, so it leads.
    assert titles[0] == 'Account Executive'
    assert set(titles[1:]) == {'Sales Development Representative', 'Applied AI Engineer'}
    assert found['jobs'][0]['matched_skills'] == ['Salesforce', 'LLM']
    assert found['jobs'][1]['matched_skills'] == ['LLM']
    assert 'description' not in found['jobs'][0] and found['charged_results'] == len(charged) == 3


def test_matched_skills_are_whole_words_and_not_case_sensitive():
    job = {'title': 'Backend Engineer (Go)', 'content_text': 'Good knowledge of C++ and postgres is a plus.'}
    assert mcp_server.matched_skills(job, ['go', 'C++', 'PostgreSQL', 'Postgres', 'C']) == ['go', 'C++', 'Postgres']
    assert mcp_server.matched_skills({'title': 'Goalkeeper coach'}, ['Go']) == []


def test_search_jobs_stops_at_the_spending_limit(charged):
    charged.limit = 1  # the second push is not charged: the user's limit is used up
    server = build_server(fake_client(ROUTES, []))
    found = call(server, 'search_jobs', companies=['warp'])
    assert len(found['jobs']) == 1 and 'spending limit' in found['note']


def test_http_app_answers_apifys_readiness_probe_and_mcp_requests_from_any_host():
    app = build_server(fake_client(ROUTES, [])).streamable_http_app(
        streamable_http_path='/mcp', stateless_http=True, json_response=True,
        transport_security=mcp_server.TransportSecuritySettings(enable_dns_rebinding_protection=False))
    with TestClient(app, base_url='https://user--ats-jobs-mcp-server.apify.actor') as client:
        ready = client.get('/', headers={'x-apify-container-server-readiness-probe': '1'})
        assert ready.status_code == 200 and ready.text == 'ok'
        init = client.post('/mcp', headers={'accept': 'application/json, text/event-stream'}, json={
            'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
            'params': {'protocolVersion': '2025-06-18', 'capabilities': {},
                       'clientInfo': {'name': 'test', 'version': '1'}}})
        assert init.status_code == 200, init.text
        assert init.json()['result']['serverInfo']['name'] == 'ats-jobs'
