"""Publish a new Actor once it has proved itself: one test run with the default input, then make it public.

The owner's merge is the approval (QUESTIONS Q25). The test is the one Apify's
daily check makes: a run with the default input must succeed and return results
within `publisher.test_run_timeout_seconds`. The Actor must also have its
pay-per-event pricing first, so it never goes public free. Anything short of
that leaves it private, and the caller opens an issue with the reason.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.common.http import PoliteClient
from factory.publisher.pricing import ITEM_EVENT, current_record

FINISHED = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"}


@dataclass
class PublishResult:
    published: bool
    reason: str
    run_url: str = ""
    results: int = 0


def default_input(actor_dir: Path) -> dict[str, Any]:
    """The input a user sees first: each field's prefill, else its default (what Apify's daily test runs)."""
    schema = json.loads((actor_dir / ".actor" / "input_schema.json").read_text(encoding="utf-8"))
    values: dict[str, Any] = {}
    for name, field in (schema.get("properties") or {}).items():
        if "prefill" in field:
            values[name] = field["prefill"]
        elif "default" in field:
            values[name] = field["default"]
    return values


def has_paid_pricing(actor: dict[str, Any], now: Any) -> bool:
    record = current_record(actor.get("pricingInfos") or [], now)
    return bool(record and record.get("pricingModel") == "PAY_PER_EVENT"
                and ITEM_EVENT in (record.get("pricingPerEvent") or {}).get("actorChargeEvents", {}))


def verify_and_publish(http: PoliteClient, api_base: str, actor: dict[str, Any], run_input: dict[str, Any], token: str,
                       timeout: int, now: Any, sleep: Any = time.sleep) -> PublishResult:
    if actor.get("isPublic"):
        return PublishResult(True, "already public")
    if not has_paid_pricing(actor, now):
        return PublishResult(False, "no pay-per-event pricing on Apify yet, so it stays private rather than go public free")
    headers = {"Authorization": f"Bearer {token}"}
    started = http.request("POST", f"{api_base}/acts/{actor['id']}/runs", json=run_input,
                           params={"waitForFinish": min(timeout, 60)}, headers=headers)
    if started.status_code not in (200, 201):
        return PublishResult(False, f"the test run could not start (HTTP {started.status_code}): {started.text[:200]}")
    run = started.json().get("data") or {}
    run_url = f"https://console.apify.com/actors/{actor['id']}/runs/{run.get('id')}"
    deadline = time.monotonic() + timeout
    while run.get("status") not in FINISHED and time.monotonic() < deadline:
        sleep(5)
        polled = http.get(f"{api_base}/actor-runs/{run['id']}", params={"waitForFinish": 60}, headers=headers)
        run = (polled.json().get("data") or run) if polled.status_code == 200 else run
    if run.get("status") != "SUCCEEDED":
        return PublishResult(False, f"the test run ended {run.get('status', 'without a status')}, not SUCCEEDED", run_url)
    dataset = http.get(f"{api_base}/datasets/{run.get('defaultDatasetId')}", headers=headers)
    items = int(((dataset.json().get("data") or {}).get("itemCount") or 0) if dataset.status_code == 200 else 0)
    if items < 1:
        return PublishResult(False, "the test run succeeded but returned no results; Apify's daily test would fail too",
                             run_url)
    public = http.request("PUT", f"{api_base}/acts/{actor['id']}", json={"isPublic": True}, headers=headers)
    if public.status_code != 200:
        return PublishResult(False, f"Apify refused to publish (HTTP {public.status_code}): {public.text[:300]}",
                             run_url, items)
    return PublishResult(True, "published", run_url, items)
