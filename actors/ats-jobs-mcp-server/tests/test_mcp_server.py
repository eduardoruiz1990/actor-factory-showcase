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


# A second, smaller board under the same name, as 'ramp' and 'warp' have on Greenhouse.
NAMESAKE = {'jobs': [{'id': 1, 'title': 'Copy of Chief Legal Officer', 'company_name': 'WARP',
                      'location': {'name': 'dublin'},
                      'absolute_url': 'https://job-boards.greenhouse.io/warp/jobs/1',
                      'updated_at': '2026-10-23T04:49:35-04:00'}], 'meta': {'total': 1}}
NAMESAKE_ROUTES = ROUTES | {
    'boards-api.greenhouse.io/v1/boards/warp/jobs?pay_transparency=true': httpx2.Response(200, json=NAMESAKE),
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


def test_a_name_on_several_platforms_uses_the_board_with_most_jobs_and_reports_the_others(charged):
    server = build_server(fake_client(NAMESAKE_ROUTES, []))
    found = call(server, 'find_job_board', company='warp')
    assert found == {'company': 'warp', 'board': 'ashby:warp', 'platform': 'ashby', 'open_jobs': 3,
                     'other_boards': {'warp': 1}}
    jobs = call(server, 'search_jobs', companies=['warp'], title_keywords=['account'])
    # Greenhouse answers first, but its stale board must not hide the real one.
    assert jobs['boards'] == {'warp': 'ashby:warp'} and jobs['other_boards'] == {'warp': {'warp': 1}}
    assert [j['title'] for j in jobs['jobs']] == ['Account Executive'] and len(charged) == 1


def test_an_explicit_board_reads_only_that_board(charged):
    seen = []
    server = build_server(fake_client(NAMESAKE_ROUTES, seen))
    found = call(server, 'search_jobs', companies=['https://job-boards.greenhouse.io/warp'])
    assert found['boards'] == {'https://job-boards.greenhouse.io/warp': 'warp'} and 'other_boards' not in found
    assert [j['title'] for j in found['jobs']] == ['Copy of Chief Legal Officer']
    assert not any('ashbyhq' in target for target in seen)


def test_a_tie_keeps_the_earlier_platform(charged):
    tied = {'jobs': NAMESAKE['jobs'] * 3, 'meta': {'total': 3}}
    routes = ROUTES | {
        'boards-api.greenhouse.io/v1/boards/warp/jobs?pay_transparency=true': httpx2.Response(200, json=tied),
    }
    found = call(build_server(fake_client(routes, [])), 'find_job_board', company='warp')
    assert found['board'] == 'warp' and found['other_boards'] == {'ashby:warp': 3}


DIRECTORY = {'boards': {
    'lever:zoox': {'company': None, 'jobs': [['Partner', 'CA']]},
    'ashby:warp': {'company': None, 'jobs': [['Account Executive', 'New York'], ['Applied AI Engineer', 'New York']]},
    'lever:nobody': {'company': None, 'jobs': [['Account Executive', 'Gone']]},
}}
DIRECTORY_ROUTES = ROUTES | {
    f'api.apify.com/v2/key-value-stores/{mcp_server.directory.STORE_ID}/records/index.json.gz':
        httpx2.Response(200, json=DIRECTORY),
}


def test_search_all_companies_needs_no_company_names_and_reads_only_matching_boards(charged):
    seen = []
    found = call(build_server(fake_client(DIRECTORY_ROUTES, seen)), 'search_all_companies', title_keywords=['account'])
    assert [j['title'] for j in found['jobs']] == ['Account Executive'] and found['charged_results'] == len(charged) == 1
    assert found['boards_matched'] == 2 and found['boards_read'] == 2  # one listed board answers 404 and is skipped
    assert not any('zoox' in target for target in seen)


def test_search_all_companies_stops_reading_once_it_has_enough(charged):
    seen = []
    found = call(build_server(fake_client(DIRECTORY_ROUTES, seen)), 'search_all_companies', title_keywords=['account'],
                 max_results=1)
    assert found['boards_matched'] == 2 and found['boards_read'] == 1 and len(found['jobs']) == 1
    assert not any('nobody' in target for target in seen)


def board_jobs(board, count):
    return httpx2.Response(200, json={'meta': {'total': count}, 'jobs': [
        {'id': n + 1, 'title': f'Engineer {board} {n}', 'company_name': board, 'location': {'name': 'Remote'},
         'absolute_url': f'https://job-boards.greenhouse.io/{board}/jobs/{n}', 'updated_at': '2026-11-01T00:00:00-04:00'}
        for n in range(count)]})


def directory_of(sizes):
    """A directory and live boards, each holding `size` engineering jobs."""
    index = {'boards': {board: {'company': board, 'jobs': [['Engineer', 'Remote']] * size} for board, size in sizes.items()}}
    return {f'api.apify.com/v2/key-value-stores/{mcp_server.directory.STORE_ID}/records/index.json.gz':
            httpx2.Response(200, json=index)} | {
        f'boards-api.greenhouse.io/v1/boards/{board}/jobs?pay_transparency=true': board_jobs(board, size)
        for board, size in sizes.items()}


def test_search_all_companies_does_not_let_one_big_company_fill_the_answer(charged):
    routes = directory_of({'big': 30, 'mid': 3, 'small': 1})
    found = call(build_server(fake_client(routes, [])), 'search_all_companies', title_keywords=['engineer'], max_results=7)
    boards = [job['board_token'] for job in found['jobs']]
    assert boards == ['big', 'mid', 'small', 'big', 'mid', 'big', 'mid'] and len(charged) == 7


def test_search_all_companies_reads_several_boards_even_when_the_first_could_fill_the_answer(charged):
    seen = []
    routes = directory_of({f'b{n}': 30 - n for n in range(8)})
    found = call(build_server(fake_client(routes, seen)), 'search_all_companies', title_keywords=['engineer'], max_results=25)
    assert found['boards_matched'] == 8 and found['boards_read'] == mcp_server.BOARDS_TO_MIX
    assert {job['board_token'] for job in found['jobs']} == {'b0', 'b1', 'b2', 'b3', 'b4'} and len(found['jobs']) == 25
    assert not any('b5' in target for target in seen)


def test_mixing_companies_still_puts_the_best_skill_matches_first():
    job = lambda board: {'platform': 'greenhouse', 'board_token': board}  # noqa: E731
    picked = [(job('a'), ['Go', 'SQL']), (job('a'), ['Go', 'SQL']), (job('a'), ['Go']), (job('b'), ['Go'])]
    mixed = mcp_server.take_turns(picked, 3)
    assert [(pair[0]['board_token'], len(pair[1])) for pair in mixed] == [('a', 2), ('a', 2), ('b', 1)]


def test_search_all_companies_needs_a_keyword_and_charges_nothing_without_one(charged):
    found = call(build_server(fake_client(DIRECTORY_ROUTES, [])), 'search_all_companies', skills=['Python'])
    assert 'keyword' in found['note'] and found['jobs'] == [] and charged == []


def test_search_all_companies_says_so_when_the_directory_is_unavailable(charged):
    found = call(build_server(fake_client(ROUTES, [])), 'search_all_companies', title_keywords=['account'])
    assert 'could not be read' in found['note'] and found['jobs'] == [] and charged == []


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
