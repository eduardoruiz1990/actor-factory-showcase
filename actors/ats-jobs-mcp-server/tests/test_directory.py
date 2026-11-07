"""The company directory: reading the index and choosing boards from it."""

import asyncio
import gzip
import json

import httpx2
import pytest

from my_actor import directory
from my_actor.polite import PoliteClient
from my_actor.source import Settings

INDEX = {'built_at': '2026-11-08T03:40:00+00:00', 'boards': {
    'small': {'company': 'Small', 'jobs': [['Data Engineer', 'Berlin'], ['Designer', 'Berlin']]},
    'big': {'company': 'Big', 'jobs': [['Data Engineer', 'Berlin'], ['Data Analyst', 'Berlin'], ['Data Lead', 'Paris']]},
    'ashby:paris': {'company': None, 'jobs': [['Data Engineer', 'Paris']]},
    'ashby:none': {'company': None, 'jobs': [['Chef', None]]},
}}


def client(response):
    async def no_sleep(_):
        return None

    return PoliteClient(min_interval=0, max_retries=0, sleep=no_sleep,
                        transport=httpx2.MockTransport(lambda request: response))


def settings(**keywords):
    return Settings(board_tokens=[], max_results=10, max_requests_per_second=1.0, **keywords)


def test_boards_with_a_match_come_first_by_number_of_matches():
    assert directory.matching_boards(INDEX, settings(title_keywords=['data'])) == ['big', 'small', 'ashby:paris']


def test_title_and_location_must_both_match():
    found = directory.matching_boards(INDEX, settings(title_keywords=['data'], location_keywords=['berlin']))
    assert found == ['big', 'small']
    assert directory.matching_boards(INDEX, settings(title_keywords=['astronaut'])) == []


def test_a_job_without_a_location_or_a_damaged_entry_breaks_nothing():
    damaged = {'boards': {'a': 'oops', 'b': {'jobs': 'oops'}, 'c': {'jobs': [['Chef'], 7, ['Chef', None]]}}}
    assert directory.matching_boards(damaged, settings(title_keywords=['chef'])) == ['c']


@pytest.mark.parametrize('body', [json.dumps(INDEX).encode(), gzip.compress(json.dumps(INDEX).encode())])
def test_the_index_loads_unpacked_or_as_raw_gzip(body):
    assert asyncio.run(directory.load(client(httpx2.Response(200, content=body))))['built_at'] == INDEX['built_at']


@pytest.mark.parametrize('response', [httpx2.Response(404), httpx2.Response(200, content=b'not json'),
                                      httpx2.Response(200, json={'no': 'boards'})])
def test_an_unreadable_index_says_so(response):
    with pytest.raises(directory.DirectoryUnavailable, match='could not be read'):
        asyncio.run(directory.load(client(response)))
