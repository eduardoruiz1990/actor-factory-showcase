"""Parsing and fetching for the Greenhouse, Lever and Ashby job board APIs, offline against saved responses.

Fixtures (fetched with tests.fetch_fixture):
- airbnb_jobs.json: boards-api.greenhouse.io /v1/boards/airbnb/jobs, trimmed to four jobs.
- airbnb_job.json: /v1/boards/airbnb/jobs/7789554, one job with content, departments and offices,
  the same shape as each job in /jobs?content=true.
- airbnb_board.json: /v1/boards/airbnb.
- lever_zoox.json: api.lever.co /v0/postings/zoox?mode=json&limit=2, postings with a salary range.
- lever_spotify.json: /v0/postings/spotify?mode=json&limit=1, a posting without one.
- ashby_warp.json: api.ashbyhq.com /posting-api/job-board/warp?includeCompensation=true, trimmed to three
  jobs: two that show a salary on the posting, one that does not. Investor names blanked.
"""

import asyncio
import json
from pathlib import Path

import httpx2
import pytest

from my_actor.polite import PoliteClient
from my_actor.privacy import clean
from my_actor.robots import RobotsCache
from my_actor.source import (
    Settings, board_key, board_token, html_to_text, iter_items, matches, parse_ashby_jobs, parse_job, parse_jobs,
    parse_lever_jobs,
)

FIXTURES = Path(__file__).parent / 'fixtures'
JOBS = json.loads((FIXTURES / 'airbnb_jobs.json').read_text())
JOB = json.loads((FIXTURES / 'airbnb_job.json').read_text())
BOARD = json.loads((FIXTURES / 'airbnb_board.json').read_text())
ZOOX = json.loads((FIXTURES / 'lever_zoox.json').read_text())
SPOTIFY = json.loads((FIXTURES / 'lever_spotify.json').read_text())
WARP = json.loads((FIXTURES / 'ashby_warp.json').read_text())
FIELDS = {
    'platform', 'board_token', 'company', 'job_id', 'internal_job_id', 'requisition_id', 'title', 'location',
    'department', 'departments', 'office', 'offices', 'absolute_url', 'language', 'updated_at', 'first_published',
    'content', 'content_text', 'employment_type', 'workplace_type', 'salary_min', 'salary_max', 'salary_currency',
    'salary_interval', 'fetched_at',
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
    assert item['platform'] == 'greenhouse' and item['salary_min'] is None and item['employment_type'] is None
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
    items, _ = collect(settings(boardTokens=['acme']), {**ROBOTS, '/v1/boards/acme/jobs?content=true&pay_transparency=true': httpx2.Response(200, json={'jobs': [], 'meta': {'total': 0}})})
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
        '/v1/boards/airbnb/jobs?content=true&pay_transparency=true': httpx2.Response(200, json={'jobs': [JOB], 'meta': {'total': 1}}),
        '/v1/boards/broken/jobs?content=true&pay_transparency=true': httpx2.Response(200, text='<html>not json</html>'),
        '/v1/boards/down/jobs?content=true&pay_transparency=true': httpx2.Response(500),
    }
    items, seen = collect(settings(boardTokens=['missing', 'broken', 'down', 'airbnb']), routes)
    assert [i['job_id'] for i in items] == [7789554]
    assert seen.count('/robots.txt') == 1
    assert seen.count('/v1/boards/airbnb/jobs?content=true&pay_transparency=true') == 1


def test_include_content_false_asks_for_the_light_list():
    routes = {**ROBOTS, '/v1/boards/airbnb/jobs?pay_transparency=true': httpx2.Response(200, json=JOBS)}
    items, seen = collect(settings(includeContent=False), routes)
    assert len(items) == 4 and '/v1/boards/airbnb/jobs?pay_transparency=true' in seen


def test_greenhouse_pay_ranges_fill_the_salary_fields():
    # Real Airbnb jobs: a plain range, one range per country, a monthly range, and a job without a range.
    pay = json.loads((FIXTURES / 'airbnb_jobs_pay.json').read_text())
    items = parse_jobs('airbnb', pay)
    assert all(set(i) == FIELDS for i in items)
    salaries = [(i['salary_min'], i['salary_max'], i['salary_currency'], i['salary_interval']) for i in items]
    assert salaries == [
        (102000, 120000, 'USD', None),
        (74000, 92000, 'EUR', 'per-year-salary'),
        (43500, 48333, 'MXN', 'per-month-salary'),
        (None, None, None, None),
    ]
    odd = parse_jobs('acme', {'jobs': [{'id': 1, 'pay_input_ranges': [{'min_cents': 1234567, 'max_cents': True}]}]})
    assert (odd[0]['salary_min'], odd[0]['salary_max'], odd[0]['salary_currency']) == (12345.67, None, None)


def test_company_falls_back_to_the_board_name():
    job = {k: v for k, v in JOB.items() if k != 'company_name'}
    routes = {**ROBOTS, '/v1/boards/airbnb/jobs?content=true&pay_transparency=true': httpx2.Response(200, json={'jobs': [job]}),
              '/v1/boards/airbnb': httpx2.Response(200, json=BOARD)}
    items, _ = collect(settings(), routes)
    assert items[0]['company'] == 'Airbnb'


def test_robots_disallow_means_no_api_request():
    routes = {'/robots.txt': httpx2.Response(200, text='User-agent: *\nDisallow: /v1/\n'),
              '/v1/boards/airbnb/jobs?content=true&pay_transparency=true': httpx2.Response(200, json={'jobs': [JOB]})}
    items, seen = collect(settings(), routes)
    assert items == [] and seen == ['/robots.txt']


def test_unreadable_robots_means_no_api_request():
    routes = {'/robots.txt': httpx2.Response(503),
              '/v1/boards/airbnb/jobs?content=true&pay_transparency=true': httpx2.Response(200, json={'jobs': [JOB]})}
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


def test_several_boards_on_one_line_are_split():
    # A first run on the Store had 'airbnb, lever:zoox' typed as one entry and found no board.
    s = Settings.from_input({'boardTokens': ['airbnb, lever:zoox', 'stripe;  https://jobs.lever.co/palantir\nairbnb']})
    assert s.board_tokens == ['airbnb', 'lever:zoox', 'stripe', 'lever:palantir']
    assert Settings.from_input({'boardTokens': 'airbnb,lever:zoox'}).board_tokens == ['airbnb', 'lever:zoox']
    assert Settings.from_input({'boardTokens': ['Acme Corp, airbnb']}).board_tokens == ['airbnb']
    assert Settings.from_input({'boardTokens': [{'url': 'https://boards.greenhouse.io/airbnb'}]}).board_tokens == ['airbnb']


def test_parses_real_lever_postings_with_salary():
    items = parse_lever_jobs('zoox', ZOOX)
    assert len(items) == 2 and all(set(i) == FIELDS for i in items)
    item = items[0]
    assert item['platform'] == 'lever' and item['board_token'] == 'zoox' and item['company'] is None
    assert item['job_id'] == ZOOX[0]['id'] and item['title'] == ZOOX[0]['text']
    assert item['location'] == 'Foster City, CA' and item['offices'] == ['Foster City, CA']
    assert item['departments'] == ['Executive Office'] and item['department'] == 'Executive Office'  # team == department
    assert item['employment_type'] == 'Full-time' and item['workplace_type'] == ZOOX[0]['workplaceType']
    assert (item['salary_min'], item['salary_currency'], item['salary_interval']) == (
        ZOOX[0]['salaryRange']['min'], 'USD', 'per-year-salary')
    assert item['absolute_url'] == ZOOX[0]['hostedUrl']
    assert item['first_published'].endswith('+00:00') and item['first_published'][:4] >= '2020'
    assert item['content'].count('<h3>') == len(ZOOX[0]['lists'])
    assert '<' not in item['content_text'] and ZOOX[0]['lists'][0]['text'].strip() in item['content_text'].splitlines()
    assert items[1]['departments'] == ['Product, Features & Homologation', 'Product and Experience']
    assert clean(item) == item  # nothing in a real posting trips the privacy guard


def test_parses_a_real_lever_posting_without_salary():
    [item] = parse_lever_jobs('spotify', SPOTIFY)
    assert item['salary_min'] is item['salary_max'] is item['salary_currency'] is None
    assert item['employment_type'] == 'Permanent' and item['location'] == 'New York, NY'


@pytest.mark.parametrize('data', [None, {'ok': False, 'error': 'Document not found'}, 'nope'])
def test_malformed_lever_response_is_rejected(data):
    with pytest.raises(ValueError):
        parse_lever_jobs('acme', data)


def test_lever_odd_values_are_tolerated():
    data = ['x', {'text': 'no id'}, {'id': 'a1', 'text': ' T ', 'categories': 'bad', 'createdAt': 'soon',
                                     'salaryRange': {'min': 'lots'}, 'lists': ['bad', {'text': 'Do', 'content': '<li>x</li>'}]}]
    [item] = parse_lever_jobs('acme', data)
    assert item['job_id'] == 'a1' and item['title'] == 'T' and item['location'] is None and item['offices'] == []
    assert item['first_published'] is None and item['salary_min'] is None
    assert item['content_text'].splitlines() == ['Do', 'x']


def test_fetches_lever_boards_politely_with_their_own_robots():
    routes = {**ROBOTS, '/v0/postings/zoox?mode=json': httpx2.Response(200, json=ZOOX),
              '/v0/postings/empty?mode=json': httpx2.Response(200, json=[]),
              '/v0/postings/gone?mode=json': httpx2.Response(404, json={'ok': False, 'error': 'Document not found'})}
    items, seen = collect(settings(boardTokens=['lever:gone', 'lever:empty', 'https://jobs.lever.co/zoox']), routes)
    assert [i['title'] for i in items] == [p['text'] for p in ZOOX]
    assert seen.count('/robots.txt') == 1 and seen.count('/v0/postings/zoox?mode=json') == 1


def test_lever_include_content_false_drops_the_description():
    routes = {**ROBOTS, '/v0/postings/zoox?mode=json': httpx2.Response(200, json=ZOOX)}
    items, _ = collect(settings(boardTokens=['lever:zoox'], includeContent=False), routes)
    assert len(items) == 2 and all(i['content'] is None and i['content_text'] is None for i in items)
    assert items[0]['salary_min'] is not None  # the light list keeps everything else


def test_lever_robots_disallow_means_no_api_request():
    routes = {'/robots.txt': httpx2.Response(200, text='User-agent: *\nDisallow: /v0/\n'),
              '/v0/postings/zoox?mode=json': httpx2.Response(200, json=ZOOX)}
    items, seen = collect(settings(boardTokens=['lever:zoox']), routes)
    assert items == [] and seen == ['/robots.txt']


def test_parses_real_ashby_jobs_with_the_salary_the_posting_shows():
    items = parse_ashby_jobs('warp', WARP)
    assert len(items) == 3 and all(set(i) == FIELDS for i in items)
    first = items[0]
    assert first['platform'] == 'ashby' and first['board_token'] == 'warp' and first['company'] is None
    assert first['job_id'] == '8fa78ab4-b9bf-4856-995a-f0c930aefa2e'
    assert first['title'] == 'Sales Development Representative' and first['location'] == 'New York'
    assert first['absolute_url'] == 'https://jobs.ashbyhq.com/warp/8fa78ab4-b9bf-4856-995a-f0c930aefa2e'
    assert first['updated_at'] == '2025-10-10T16:31:25.268+00:00' and first['first_published'] is None
    assert (first['employment_type'], first['workplace_type']) == ('Full-time', 'onsite')
    assert (first['salary_min'], first['salary_max'], first['salary_currency'], first['salary_interval']) == (
        105000, 140000, 'USD', 'per-year-salary')
    assert first['content'].startswith('<') and first['content_text'] and '[name removed]' in first['content_text']
    assert items[1]['salary_min'] == 160000
    hidden = items[2]  # the company does not show pay on this posting
    assert hidden['title'] == 'Applied AI Engineer' and hidden['salary_min'] is None and hidden['salary_interval'] is None


def test_ashby_hidden_pay_unlisted_jobs_and_locations():
    job = dict(WARP['jobs'][0], shouldDisplayCompensationOnJobPostings=False,
               secondaryLocations=[{'location': 'Remote'}, {'location': 'New York'}, {}], team='Growth')
    unlisted = dict(WARP['jobs'][1], isListed=False)
    [item] = parse_ashby_jobs('warp', {'jobs': [job, unlisted, {'title': 'no id'}]})
    assert item['salary_min'] is None  # Ashby sent a salary, but the company keeps it off the posting
    assert item['offices'] == ['New York', 'Remote'] and item['departments'] == [job['department'], 'Growth']
    [light] = parse_ashby_jobs('warp', WARP, include_content=False)[:1]
    assert light['content'] is None and light['content_text'] is None and light['salary_min'] == 105000


@pytest.mark.parametrize('data', [[], {'jobs': 'x'}, 'oops'])
def test_malformed_ashby_response_is_rejected(data):
    with pytest.raises(ValueError):
        parse_ashby_jobs('acme', data)


def test_fetches_ashby_boards_although_its_robots_txt_answers_401():
    # Ashby's API answers /robots.txt with 401: RFC 9309 reads that as no robots.txt (Q19).
    routes = {'/robots.txt': httpx2.Response(401),
              '/posting-api/job-board/warp?includeCompensation=true': httpx2.Response(200, json=WARP),
              '/posting-api/job-board/gone?includeCompensation=true': httpx2.Response(404, text='Not Found')}
    items, seen = collect(settings(boardTokens=['ashby:gone', 'https://jobs.ashbyhq.com/Warp']), routes)
    assert [i['title'] for i in items] == [j['title'] for j in WARP['jobs']]
    assert seen.count('/robots.txt') == 1


@pytest.mark.parametrize(('value', 'key'), [
    ('airbnb', 'airbnb'),
    ('greenhouse:Airbnb', 'airbnb'),
    ('lever:Palantir', 'lever:palantir'),
    ('lever-eu:acme', 'lever-eu:acme'),
    ('https://jobs.lever.co/palantir', 'lever:palantir'),
    ('https://jobs.lever.co/palantir/6ed76ce8-4156-4b60-b120-403538bd66cd/apply', 'lever:palantir'),
    ('jobs.eu.lever.co/acme', 'lever-eu:acme'),
    ('https://api.lever.co/v0/postings/zoox?mode=json', 'lever:zoox'),
    ('https://boards.greenhouse.io/airbnb', 'airbnb'),
    ('ashby:Ramp', 'ashby:ramp'),
    ('https://jobs.ashbyhq.com/Warp', 'ashby:warp'),
    ('https://jobs.ashbyhq.com/warp/8fa78ab4-b9bf-4856-995a-f0c930aefa2e/application', 'ashby:warp'),
    ('https://api.ashbyhq.com/posting-api/job-board/warp?includeCompensation=true', 'ashby:warp'),
    ('https://jobs.ashbyhq.com/', None),
    ('lever:', None),
    ('lever:not a site', None),
    ('https://jobs.lever.co/', None),
    ('https://lever.co.evil.example/x', None),
    ('workday:acme', None),
])
def test_board_key(value, key):
    assert board_key(value) == key
