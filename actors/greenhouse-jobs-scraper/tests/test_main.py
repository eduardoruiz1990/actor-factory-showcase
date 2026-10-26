"""End-to-end: local Actor runs (each in a fresh process) against a fake Greenhouse API, with Apify's local storage."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from my_actor.source import Settings

from .conftest import dataset_items

ROOT = Path(__file__).resolve().parents[1]
PRICING = {
    'pricingModel': 'PAY_PER_EVENT',
    'apifyMarginPercentage': 0.2,
    'createdAt': '2026-01-01T00:00:00.000Z',
    'startedAt': '2026-01-01T00:00:00.000Z',
    'pricingPerEvent': {'actorChargeEvents': {
        'apify-default-dataset-item': {'eventTitle': 'Result', 'eventDescription': 'One result', 'eventPriceUsd': 0.01},
    }},
}


def run(storage, n, max_results=100, **env):
    tokens = ['blocked-5', f'acme-{n}', 'missing']
    settings = {'board_tokens': tokens, 'max_results': max_results, 'max_requests_per_second': 1}
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith(('APIFY_', 'ACTOR_', 'CRAWLEE_'))}
    clean_env.update(APIFY_LOCAL_STORAGE_DIR=str(storage), CRAWLEE_STORAGE_DIR=str(storage), **env)
    done = subprocess.run([sys.executable, '-m', 'tests.local_run', json.dumps(settings)], cwd=ROOT, env=clean_env,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])['pushed']


def test_pushes_clean_jobs_and_skips_disallowed_and_unknown_boards(tmp_path):
    assert run(tmp_path, 3) == 3
    items = dataset_items(tmp_path)
    assert [i['title'] for i in items] == ['Engineer 1', 'Engineer 2', 'Engineer 3']
    assert {i['board_token'] for i in items} == {'acme-3'}
    assert items[0]['department'] == 'Engineering' and items[0]['company'] == 'Acme'
    assert all('jobs@example.com' not in i['content'] + i['content_text'] for i in items)


def test_stops_at_max_results(tmp_path):
    assert run(tmp_path, 5, max_results=2) == 2
    assert len(dataset_items(tmp_path)) == 2


def test_stops_at_the_users_spending_limit(tmp_path):
    # The event must appear in the counts: an empty {} reads as unset and the SDK ignores the test pricing.
    pushed = run(tmp_path, 5, APIFY_ACTOR_PRICING_INFO=json.dumps(PRICING), APIFY_CHARGED_ACTOR_EVENT_COUNTS='{"apify-default-dataset-item": 0}',
                 ACTOR_MAX_TOTAL_CHARGE_USD='0.025')  # pays for two results
    assert pushed == 2
    assert len(dataset_items(tmp_path)) == 2


def test_a_spending_limit_without_pay_per_event_does_not_stop_the_run(tmp_path):
    # Before monetization is set up the SDK reports the limit as reached on every push; results must still flow.
    assert run(tmp_path, 3, ACTOR_MAX_TOTAL_CHARGE_USD='0.025') == 3
    assert len(dataset_items(tmp_path)) == 3


def test_settings_validation():
    with pytest.raises(ValueError, match='boardTokens'):
        Settings.from_input({})
    with pytest.raises(ValueError, match='boardTokens'):
        Settings.from_input({'boardTokens': ['  ', 'not a token!']})
    s = Settings.from_input({'boardTokens': [' Airbnb ', 'https://boards.greenhouse.io/airbnb', 'stripe'],
                             'maxRequestsPerSecond': 50, 'titleKeywords': 'Engineer, data '})
    assert s.board_tokens == ['airbnb', 'stripe'] and s.max_requests_per_second == 1.0 and s.max_results == 1000
    assert s.include_content is True and s.title_keywords == ['engineer', 'data'] and s.location_keywords == []
    assert Settings.from_input({'boardTokens': ['a'], 'includeContent': False}).include_content is False
