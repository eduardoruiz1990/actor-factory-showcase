import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from factory.common.http import PoliteClient
from factory.publisher.publish import default_input, verify_and_publish

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.apify.com/v2"
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
PRICED = [{"pricingModel": "PAY_PER_EVENT", "startedAt": "2026-11-01T11:00:00.000Z",
           "pricingPerEvent": {"actorChargeEvents": {"apify-default-dataset-item": {"eventTitle": "Result"}}}}]
ACTOR = {"id": "ACT1", "isPublic": False, "pricingInfos": PRICED}


def fake_api(statuses=("RUNNING", "SUCCEEDED"), items=12, publish_status=200):
    seen, polls = [], list(statuses)

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(201, json={"data": {"id": "RUN1", "status": polls.pop(0), "defaultDatasetId": "DS1"}})
        if request.url.path.startswith("/v2/actor-runs/"):
            return httpx.Response(200, json={"data": {"id": "RUN1", "status": polls.pop(0), "defaultDatasetId": "DS1"}})
        if request.url.path.startswith("/v2/datasets/"):
            return httpx.Response(200, json={"data": {"itemCount": items}})
        return httpx.Response(publish_status, json={"data": {"isPublic": True}})

    http = PoliteClient(user_agent="t", min_interval=0, max_retries=0, transport=httpx.MockTransport(handler))
    return http, seen


def run(http, actor=ACTOR):
    return verify_and_publish(http, API, actor, {"boardTokens": ["airbnb"]}, "secret", 300, NOW, sleep=lambda s: None)


def test_a_successful_test_run_with_results_publishes_the_actor():
    http, seen = fake_api()
    result = run(http)
    assert result.published and result.results == 12 and result.run_url.endswith("/runs/RUN1")
    assert seen == [("POST", "/v2/acts/ACT1/runs"), ("GET", "/v2/actor-runs/RUN1"), ("GET", "/v2/datasets/DS1"),
                    ("PUT", "/v2/acts/ACT1")]


def test_a_failed_or_empty_run_keeps_the_actor_private():
    http, seen = fake_api(statuses=("FAILED",))
    result = run(http)
    assert not result.published and "ended FAILED" in result.reason and ("PUT", "/v2/acts/ACT1") not in seen
    http, seen = fake_api(statuses=("SUCCEEDED",), items=0)
    result = run(http)
    assert not result.published and "no results" in result.reason and ("PUT", "/v2/acts/ACT1") not in seen


def test_no_pricing_means_no_test_run_and_no_publishing():
    http, seen = fake_api()
    result = run(http, {**ACTOR, "pricingInfos": []})
    assert not result.published and "go public free" in result.reason and seen == []


def test_apify_refusing_to_publish_is_reported():
    http, _ = fake_api(statuses=("SUCCEEDED",), publish_status=400)
    result = run(http)
    assert not result.published and "Apify refused to publish (HTTP 400)" in result.reason


def test_the_test_run_uses_the_prefilled_input():
    jobs = default_input(ROOT / "actors" / "greenhouse-jobs-scraper")
    schema = json.loads((ROOT / "actors" / "greenhouse-jobs-scraper" / ".actor" / "input_schema.json").read_text())
    assert jobs["boardTokens"] == schema["properties"]["boardTokens"]["prefill"]
    assert jobs["onlyNew"] is False  # a default, so the test run returns results, not only new ones
