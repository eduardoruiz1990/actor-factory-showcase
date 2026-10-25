"""Parsing and fetching for the Greenhouse Job Board API, offline against saved responses.

Fixtures (fetched with tests.fetch_fixture from boards-api.greenhouse.io):
- airbnb_jobs.json: /v1/boards/airbnb/jobs, trimmed to four jobs.
- airbnb_job.json: /v1/boards/airbnb/jobs/7789554, one job with content, departments and offices,
  the same shape as each job in /jobs?content=true.
- airbnb_board.json: /v1/boards/airbnb.
"""

import asyncio
import json
from pathlib import Path

import httpx2
import pytest

from my_actor.polite import PoliteClient
from my_actor.privacy import clean
from my_actor.robots import RobotsCache
from my_actor.source import Settings, board_token, html_to_text, iter_items, matches, parse_job, parse_jobs

FIXTURES = Path(__file__).parent / 'fixtures'
JOBS = json.loads((FIXTURES / 'airbnb_jobs.json').read_text())
JOB = json.loads((FIXTURES / 'airbnb_job.json').read_text())
BOARD = json.loads((FIXTURES / 'airbnb_board.json').read_text())
FIELDS = {
    'board_token', 'company', 'job_id', 'internal_job_id', 'requisition_id', 'title', 'location', 'department',
    'departments', 'office', 'offices', 'absolute_url', 'language', 'updated_at', 'first_published', 'content',
    'content_text', 'fetched_at',
}


def settings(**overrides):
    return Settings.from_input({'boardTokens': ['airbnb'], **overrides})


def collect(s, routes):
    """Run iter_items against a fake API; `routes` maps a path (with query) to a response. Returns items and requests."""
    seen = []

    def handler(request):
        target = request.url.path + (f'?{request.url.query.decode()}' if request.url.query else '')
        seen.append(target)
        route = routes.get(target, httpx2.Response(404, json={'status': 404, 'error': 'Job not found'}))
        return route() if callable(route) else route

    async def go():
        async def no_sleep(_):
            return None

        async with PoliteClient(min_interval=0, transport=httpx2.MockTransport(handler), sleep=no_sleep,
                                max_retries=1) as http:
            return [item async for item in iter_items(s, http, RobotsCache(http))]

    return asyncio.run(go()), seen


ROBOTS = {'/robots.txt': httpx2.Response(200, text='User-agent: *\nAllow: /\n')}


def test_parses_a_real_job_with_content():
    item = parse_job('airbnb', JOB, '2026-10-25T00:00:00+00:00')
    assert set(item) == FIELDS
    assert item['company'] == 'Airbnb' and item['job_id'] == 7789554 and item['requisition_id'] == 'ONE'
    assert item['title'] == 'Associate Legal Counsel, Japan' and item['location'] == 'Tokyo, Japan'
    assert item['department'] == 'Legal' and item['departments'] == ['Legal']
    assert item['office'] == 'Tokyo, Japan' and item['offices'] == ['Tokyo, Japan']
    assert item['absolute_url'] == 'https://careers.airbnb.com/positions/7789554?gh_jid=7789554'
    assert item['first_published'] == '2026-04-13T04:49:05-04:00'
    assert item['content'].startswith('<div class="content-intro"><p>')  # the API escapes HTML; output is real HTML
    assert item['content_text'].startswith('Airbnb was born in 2007')
    assert '<' not in item['content_text'] and '&nbsp;' not in item['content_text']
    assert 'The Community You Will Join:' in item['content_text'].splitlines()


def test_parses_a_real_job_list_without_content():
    items = parse_jobs('airbnb', JOBS)
    assert len(items) == JOBS['meta']['total'] == 4
    assert all(set(i) == FIELDS for i in items)
    assert all(i['content'] is None and i['content_text'] is None and i['departments'] == [] for i in items)
    assert items[0]['title'] == 'Associate Legal Counsel, Japan' and items[0]['company'] == 'Airbnb'


def test_output_carries_no_metadata_or_compliance_blocks():
    # Custom metadata fields are company-defined and could name a hiring manager; they are not passed through.
    item = parse_job('airbnb', JOB, 'now')
    assert 'metadata' not in item and 'data_compliance' not in item
    assert clean(item) == item  # nothing in a real job trips the privacy guard


def test_empty_board():
    assert parse_jobs('acme', {'jobs': [], 'meta': {'total': 0}}) == []
    items, _ = collect(settings(boardTokens=['acme']), {**ROBOTS, '/v1/boards/acme/jobs?content=true': httpx2.Response(200, json={'jobs': [], 'meta': {'total': 0}})})
    assert items == []


@pytest.mark.parametrize('data', [None, [], {'error': 'x'}, {'jobs': 'nope'}])
def test_malformed_response_is_rejected(data):
    with pytest.raises(ValueError):
        parse_jobs('acme', data)


def test_malformed_entries_are_skipped_and_odd_values_tolerated():
    data = {'jobs': ['x', None, {'title': 'no id'}, {'id': 7, 'title': ' T ', 'location': 'Berlin', 'departments': 'bad',
                                                     'offices': [None, {'name': ''}, {'name': 'Berlin'}], 'content': '   '}]}
    [item] = parse_jobs('acme', data)
    assert item['job_id'] == 7 and item['title'] == 'T' and item['location'] == 'Berlin'
    assert item['departments'] == [] and item['department'] is None and item['offices'] == ['Berlin']
    assert item['content'] is None and item['company'] is None


def test_fetches_one_request_per_board_and_continues_after_bad_boards():
    routes = {
        **ROBOTS,
        '/v1/boards/airbnb/jobs?content=true': httpx2.Response(200, json={'jobs': [JOB], 'meta': {'total': 1}}),
        '/v1/boards/broken/jobs?content=true': httpx2.Response(200, text='<html>not json</html>'),
        '/v1/boards/down/jobs?content=true': httpx2.Response(500),
    }
    items, seen = collect(settings(boardTokens=['missing', 'broken', 'down', 'airbnb']), routes)
    assert [i['job_id'] for i in items] == [7789554]
    assert seen.count('/robots.txt') == 1
    assert seen.count('/v1/boards/airbnb/jobs?content=true') == 1


def test_include_content_false_asks_for_the_light_list():
    routes = {**ROBOTS, '/v1/boards/airbnb/jobs': httpx2.Response(200, json=JOBS)}
    items, seen = collect(settings(includeContent=False), routes)
    assert len(items) == 4 and '/v1/boards/airbnb/jobs' in seen


def test_company_falls_back_to_the_board_name():
    job = {k: v for k, v in JOB.items() if k != 'company_name'}
    routes = {**ROBOTS, '/v1/boards/airbnb/jobs?content=true': httpx2.Response(200, json={'jobs': [job]}),
              '/v1/boards/airbnb': httpx2.Response(200, json=BOARD)}
    items, _ = collect(settings(), routes)
    assert items[0]['company'] == 'Airbnb'


def test_robots_disallow_means_no_api_request():
    routes = {'/robots.txt': httpx2.Response(200, text='User-agent: *\nDisallow: /v1/\n'),
              '/v1/boards/airbnb/jobs?content=true': httpx2.Response(200, json={'jobs': [JOB]})}
    items, seen = collect(settings(), routes)
    assert items == [] and seen == ['/robots.txt']


def test_unreadable_robots_means_no_api_request():
    routes = {'/robots.txt': httpx2.Response(503),
              '/v1/boards/airbnb/jobs?content=true': httpx2.Response(200, json={'jobs': [JOB]})}
    items, seen = collect(settings(), routes)
    assert items == [] and set(seen) == {'/robots.txt'}


def test_filters_by_title_and_location_keywords():
    item = parse_job('airbnb', JOB, 'now')
    assert matches(item, settings())
    assert matches(item, settings(titleKeywords=['counsel', 'engineer']))
    assert not matches(item, settings(titleKeywords=['engineer']))
    assert matches(item, settings(locationKeywords='tokyo'))
    assert not matches(item, settings(titleKeywords=['counsel'], locationKeywords=['remote']))


@pytest.mark.parametrize(('value', 'token'), [
    ('airbnb', 'airbnb'),
    (' Airbnb ', 'airbnb'),
    ('https://boards.greenhouse.io/airbnb', 'airbnb'),
    ('https://job-boards.greenhouse.io/airbnb/jobs/7789554', 'airbnb'),
    ('job-boards.eu.greenhouse.io/acme', 'acme'),
    ('https://boards.greenhouse.io/embed/job_board?for=stripe', 'stripe'),
    ('https://boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true', 'airbnb'),
    ({'url': 'https://boards.greenhouse.io/airbnb'}, None),  # dicts are unwrapped by Settings, not here
    ('https://careers.airbnb.com/positions/7789554?gh_jid=7789554', None),  # not a Greenhouse host
    ('https://greenhouse.io.evil.example/airbnb', None),
    ('airbnb.com', None),
    ('not a token!', None),
    ('', None),
    (None, None),
])
def test_board_token(value, token):
    assert board_token(value) == token


def test_html_to_text_keeps_every_block_once():
    text = html_to_text('<div>Intro<ul><li><p>One</p></li><li>Two<br>lines</li></ul></div><p>A&nbsp;&nbsp;b</p>')
    assert text.splitlines() == ['Intro', 'One', 'Two', 'lines', 'A b']


def test_default_input_is_light_and_survives_one_board_leaving():
    # Apify Store runs the Actor daily with its default input and expects results within 5 minutes.
    schema = json.loads((Path(__file__).parents[1] / '.actor' / 'input_schema.json').read_text())
    boards = schema['properties']['boardTokens']
    assert boards['default'] == boards['prefill'] and len(boards['default']) >= 2
    assert Settings.from_input({'boardTokens': boards['default']}).board_tokens == boards['default']
