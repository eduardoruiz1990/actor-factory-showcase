"""End-to-end: local Actor runs (each in a fresh process) against a fake website, with Apify's local storage."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from my_actor.source import Settings, parse_page

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


def run(storage, n, max_results=100, only_new=False, pages=None, **env):
    pages = pages if pages is not None else range(1, n + 1)
    urls = [f'https://site.example/{i}' for i in pages] + ['https://site.example/blocked']
    settings = {'start_urls': urls, 'max_results': max_results, 'max_requests_per_second': 1,
                'only_new': only_new, 'state_key': 'test-search'}
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith(('APIFY_', 'ACTOR_', 'CRAWLEE_'))}
    clean_env.update(APIFY_LOCAL_STORAGE_DIR=str(storage), CRAWLEE_STORAGE_DIR=str(storage), **env)
    done = subprocess.run([sys.executable, '-m', 'tests.local_run', json.dumps(settings)], cwd=ROOT, env=clean_env,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])['pushed']


def test_pushes_clean_results_and_skips_disallowed_pages(tmp_path):
    assert run(tmp_path, 3) == 3
    items = dataset_items(tmp_path)
    assert [i['title'] for i in items] == ['Example 1', 'Example 2', 'Example 3']
    assert all('sales@example.com' not in i['description'] for i in items)
    assert all(i['url'] != 'https://site.example/blocked' for i in items)


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


def test_only_new_returns_each_result_once_across_runs(tmp_path):
    # Scheduled runs share Apify's storage; the default dataset is emptied at the start of each run.
    assert run(tmp_path, 0, only_new=True, pages=[1, 2]) == 2
    assert run(tmp_path, 0, only_new=True, pages=[1, 2]) == 0  # nothing new, nothing charged
    assert run(tmp_path, 0, only_new=True, pages=[1, 2, 3]) == 1
    assert [i['title'] for i in dataset_items(tmp_path)] == ['Example 3']
    assert run(tmp_path, 0, pages=[1, 2, 3]) == 3  # without the switch every result is returned


def test_only_new_keeps_unreached_results_new_and_forgets_gone_ones(tmp_path):
    assert run(tmp_path, 0, only_new=True, pages=[1, 2, 3], max_results=1) == 1  # stopped early
    assert run(tmp_path, 0, only_new=True, pages=[1, 2, 3]) == 2  # 2 and 3 were never returned
    assert run(tmp_path, 0, only_new=True, pages=[2, 3]) == 0  # 1 is gone, so a complete run forgets it
    assert run(tmp_path, 0, only_new=True, pages=[1, 2, 3]) == 1  # 1 is back: new again


def test_settings_validation():
    same = Settings.from_input({'startUrls': ['https://a.example/', 'https://b.example/']})
    reordered = Settings.from_input({'startUrls': ['https://b.example/', 'https://a.example/'], 'onlyNew': True})
    assert same.state_key == reordered.state_key and reordered.only_new and not same.only_new
    named = Settings.from_input({'startUrls': ['https://c.example/'], 'monitorName': 'daily'})
    assert named.state_key == Settings.from_input({'startUrls': ['https://d.example/'], 'monitorName': 'daily'}).state_key
    assert named.state_key != same.state_key
    with pytest.raises(ValueError, match='startUrls'):
        Settings.from_input({})
    s = Settings.from_input({'startUrls': [{'url': ' https://a.example/ '}], 'maxRequestsPerSecond': 50})
    assert s.start_urls == ['https://a.example/'] and s.max_requests_per_second == 5.0 and s.max_results == 100


def test_parse_page_handles_missing_tags():
    item = parse_page('https://a.example/', '<html><body>no head</body></html>')
    assert item['title'] is None and item['description'] is None and item['language'] is None
