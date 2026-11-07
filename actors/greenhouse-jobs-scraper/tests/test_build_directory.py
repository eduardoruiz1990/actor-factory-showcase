"""The job directory builder: picking boards, leaving out excluded companies, and never losing a board that failed."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx2

from my_actor.polite import PoliteClient
from tools import build_directory as bd

WARP = json.loads((Path(__file__).parent / 'fixtures' / 'ashby_warp.json').read_text())
ALLOW = httpx2.Response(200, text='User-agent: *\nAllow: /\n')
NOW = datetime(2026, 11, 8, 3, 40, tzinfo=UTC)


def greenhouse(*titles, company='Acme'):
    return httpx2.Response(200, json={'meta': {'total': len(titles)}, 'jobs': [
        {'id': n + 1, 'title': title, 'company_name': company, 'location': {'name': 'Remote'},
         'absolute_url': f'https://job-boards.greenhouse.io/acme/jobs/{n}', 'updated_at': '2026-11-01T00:00:00-04:00'}
        for n, title in enumerate(titles)]})


def client(routes):
    """Polite clients against fake platforms; `routes` maps a board's host and path to a response, anything else is a 404."""

    def handler(request):
        if request.url.path == '/robots.txt':
            return ALLOW
        return routes.get(f'{request.url.host}{request.url.path}', httpx2.Response(404, json={'error': 'Not Found'}))

    async def no_sleep(_):
        return None

    return lambda interval: PoliteClient(min_interval=0, max_retries=0, transport=httpx2.MockTransport(handler), sleep=no_sleep)


def test_names_are_read_once_without_comments():
    assert bd.read_names('# Ramp is here\nRamp notion\n\nramp stripe\n') == ['ramp', 'notion', 'stripe']


def test_the_company_list_has_no_pharma_or_health_names():
    names = bd.read_names((Path(bd.__file__).parent / 'companies.txt').read_text())
    assert len(names) > 300
    assert [name for name in names if bd.excluded(name)] == []


def test_verify_keeps_the_board_with_most_jobs_for_a_name():
    routes = {'boards-api.greenhouse.io/v1/boards/warp/jobs': greenhouse('Copy of Chief Legal Officer', company='WARP'),
              'api.ashbyhq.com/posting-api/job-board/warp': httpx2.Response(200, json=WARP)}
    result = asyncio.run(bd.verify(['warp', 'nobody'], client(routes)))
    assert result == {'boards': {'ashby:warp': None}}


def test_verify_leaves_out_pharma_and_health_companies_even_under_a_harmless_name():
    routes = {'boards-api.greenhouse.io/v1/boards/acme/jobs': greenhouse('Engineer', company='Acme Therapeutics'),
              'boards-api.greenhouse.io/v1/boards/fine/jobs': greenhouse('Engineer', company='Fine Inc')}
    assert asyncio.run(bd.verify(['acme', 'fine'], client(routes))) == {'boards': {'fine': 'Fine Inc'}}


def test_the_index_keeps_titles_and_locations_only():
    routes = {'boards-api.greenhouse.io/v1/boards/acme/jobs': greenhouse('Engineer', 'Designer')}
    index = asyncio.run(bd.build_index({'acme': 'Acme'}, {}, NOW, client(routes)))
    assert index == {'built_at': '2026-11-08T03:40:00+00:00', 'boards': {
        'acme': {'company': 'Acme', 'jobs': [['Engineer', 'Remote'], ['Designer', 'Remote']]}}}


def test_a_board_that_fails_keeps_its_last_entry_and_an_empty_board_goes():
    last = {'acme': {'company': 'Acme', 'jobs': [['Engineer', 'Remote']]}, 'quiet': {'company': 'Q', 'jobs': [['Old', 'X']]}}
    routes = {'boards-api.greenhouse.io/v1/boards/acme/jobs': httpx2.Response(429, text='Too many requests'),
              'boards-api.greenhouse.io/v1/boards/quiet/jobs': greenhouse()}
    index = asyncio.run(bd.build_index({'acme': 'Acme', 'quiet': 'Q'}, last, NOW, client(routes)))
    assert index['boards'] == {'acme': last['acme']}


def test_each_platform_keeps_its_own_request_interval():
    seen = []

    def spy(interval):
        seen.append(interval)
        return client({})(interval)

    asyncio.run(bd.scan(['acme', 'workable:acme'], spy))
    assert sorted(seen) == [1.0, 5.0]


def counting_client(handle):
    """Directory clients against a fake `handle(request)`, with no retries and no waiting; robots.txt allows all."""

    def handler(request):
        return ALLOW if request.url.path == '/robots.txt' else handle(request)

    async def no_sleep(_):
        return None

    return lambda interval: bd.DirectoryClient(min_interval=0, max_retries=0, transport=httpx2.MockTransport(handler),
                                               sleep=no_sleep)


def test_a_platform_that_keeps_answering_429_is_left_alone_and_the_others_finish(capsys):
    asked = []

    def handle(request):
        if request.url.host == 'apply.workable.com':
            asked.append(request.url.path)
            return httpx2.Response(429)
        return greenhouse('Engineer')

    keys = [f'workable:name{n}' for n in range(20)] + ['acme']
    results = asyncio.run(bd.scan(keys, counting_client(handle)))
    assert len(asked) == bd.MAX_429_IN_A_ROW  # not one for each of the 20 boards
    assert results['acme'] is not None and 'workable:name19' not in results
    assert 'workable answered 429 3 times in a row; stopped with 18 of 20 boards not tried' in capsys.readouterr().out


def test_a_normal_answer_between_429s_keeps_the_platform_going():
    answers = iter([429, 429, 404, 429, 429, 404])
    client_ = counting_client(lambda request: httpx2.Response(next(answers)))
    results = asyncio.run(bd.scan([f'name{n}' for n in range(6)], client_))
    assert len(results) == 6


def test_a_stopped_platform_keeps_its_boards_last_entries():
    last = {'workable:acme': {'company': 'Acme', 'jobs': [['Engineer', 'Remote']]}}
    client_ = counting_client(lambda request: httpx2.Response(429))
    boards = {f'workable:{name}': None for name in ('a', 'b', 'c', 'acme')}
    assert asyncio.run(bd.build_index(boards, last, NOW, client_))['boards'] == last


def test_a_platform_out_of_time_keeps_what_it_read_and_the_others_finish(capsys):
    async def handler(request):
        if request.url.path == '/robots.txt':
            return ALLOW
        if request.url.path.endswith('/slow/jobs'):
            await asyncio.sleep(30)
        return greenhouse('Engineer')

    def client_(interval):
        return bd.DirectoryClient(min_interval=0, max_retries=0, transport=httpx2.MockTransport(handler))

    results = asyncio.run(bd.scan(['first', 'slow', 'never', 'lever:acme'], client_, budget=0.2))
    assert set(results) == {'first', 'lever:acme'} and results['first']
    assert 'greenhouse ran out of its 0 minutes; stopped with 2 of 3 boards not tried' in capsys.readouterr().out


def test_a_board_that_cannot_be_reached_is_skipped_and_the_rest_are_read():
    def handle(request):
        if 'down' in request.url.path:
            raise httpx2.ConnectError('no route')
        return greenhouse('Engineer')

    results = asyncio.run(bd.scan(['down', 'acme'], counting_client(handle)))
    assert results['down'] is None and results['acme']
