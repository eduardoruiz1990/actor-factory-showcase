import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from factory.common.http import PoliteClient
from factory.publisher.pricing import desired_tiers, load_pricing, plan_change, sync_pricing

ROOT = Path(__file__).resolve().parents[1]
# The jobs Actor's real pricing history on 2026-10-31: $1.60 per 1,000, then the same price with tier discounts.
RECORDS = json.loads((ROOT / "tests" / "fixtures" / "apify" / "pricing_infos_greenhouse.json").read_text())
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
BOUNDS = (0.1, 10.0)


def pricing(price=0.99, tiers=None, managed=True, description="One open job from a company job board."):
    tiers = {"BRONZE": 0.89, "SILVER": 0.79, "GOLD": 0.69} if tiers is None else tiers
    return {"managedByPublisher": managed, "minimalMaxTotalChargeUsd": 0.5, "events": {
        "apify-default-dataset-item": {"title": "Job", "description": description, "pricePer1000Usd": price,
                                       "tiersPer1000Usd": tiers}}}


def test_tier_prices_inherit_upwards_like_apifys_console():
    assert desired_tiers(pricing()["events"]["apify-default-dataset-item"]) == {
        "FREE": 0.00099, "BRONZE": 0.00089, "SILVER": 0.00079, "GOLD": 0.00069, "PLATINUM": 0.00069, "DIAMOND": 0.00069}


def test_a_price_cut_adds_one_record_and_keeps_the_history():
    record, reason = plan_change(pricing(), RECORDS, BOUNDS, NOW)
    assert reason == "apify-default-dataset-item: $1.6 -> $0.99 per 1,000"
    event = record["pricingPerEvent"]["actorChargeEvents"]["apify-default-dataset-item"]
    assert event["eventTieredPricingUsd"]["GOLD"] == {"tieredEventPriceUsd": 0.00069} and "eventPriceUsd" not in event
    assert event["isPrimaryEvent"] is True and event["eventTitle"] == "Job"
    # The Actor start event, the margin and the model are copied from the current record, untouched.
    current = RECORDS[-1]["pricingPerEvent"]["actorChargeEvents"]
    assert record["pricingPerEvent"]["actorChargeEvents"]["apify-actor-start"] == current["apify-actor-start"]
    assert record["apifyMarginPercentage"] == 0.2 and record["pricingModel"] == "PAY_PER_EVENT"
    assert record["startedAt"] == "2026-11-01T12:00:00.000Z"
    assert "createdAt" not in record and "notifiedAboutChangeAt" not in record


def test_increases_are_refused_and_left_to_the_owner():
    for change in (pricing(price=1.99), pricing(tiers={"BRONZE": 1.5, "SILVER": 0.79, "GOLD": 0.69})):
        record, reason = plan_change(change, RECORDS, BOUNDS, NOW)
        assert record is None and reason.startswith("refused") and "would rise" in reason


def test_a_typo_outside_the_bounds_is_refused():
    record, reason = plan_change(pricing(price=0.0099), RECORDS, BOUNDS, NOW)  # $0.0099 per 1,000: a missing digit
    assert record is None and "outside $0.1-$10 per 1,000" in reason


def test_nothing_is_sent_when_unmanaged_pending_or_already_up_to_date():
    assert plan_change(pricing(managed=False), RECORDS, BOUNDS, NOW)[1].startswith("pricing is managed in Apify Console")
    pending = [*RECORDS, {**copy.deepcopy(RECORDS[-1]), "startedAt": "2026-11-20T00:00:00.000Z"}]
    assert plan_change(pricing(), pending, BOUNDS, NOW)[1] == "a scheduled pricing change is still pending"
    applied, _ = plan_change(pricing(), RECORDS, BOUNDS, NOW)
    assert plan_change(pricing(), [*RECORDS, applied], BOUNDS, NOW)[1] == "already up to date"
    # The current price with tiers, and only the description differs: a text-only update is allowed.
    same = pricing(price=1.6, tiers={"BRONZE": 1.44, "SILVER": 1.28, "GOLD": 1.12}, description="New text.")
    assert plan_change(same, RECORDS, BOUNDS, NOW)[0] is not None


def test_sync_sends_the_history_plus_the_new_record_and_warns_on_refusal(capsys):
    sent = []

    def api(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200 if len(sent) == 1 else 400, json={"error": {"type": "cannot-add-multiple-pricing-infos"}})

    http = PoliteClient(user_agent="t", min_interval=0, max_retries=0, transport=httpx.MockTransport(api))
    url = "https://api.apify.com/v2/acts/guayox~greenhouse-jobs-scraper"
    assert sync_pricing(http, url, "secret", pricing(), RECORDS, BOUNDS, NOW)
    assert sent[0]["pricingInfos"][:2] == RECORDS and len(sent[0]["pricingInfos"]) == 3
    assert not sync_pricing(http, url, "secret", pricing(), RECORDS, BOUNDS, NOW)
    assert "Pricing not changed (HTTP 400)" in capsys.readouterr().out
    assert not sync_pricing(http, url, "secret", pricing(price=5), RECORDS, BOUNDS, NOW)  # refused before any request
    assert len(sent) == 2


def test_every_actor_pricing_file_is_sane():
    for actor_dir in sorted((ROOT / "actors").glob("*/")):
        if (actor_dir / ".actor" / "pricing.json").exists():
            event = load_pricing(actor_dir)["events"]["apify-default-dataset-item"]
            prices = desired_tiers(event)
            assert all(0.1 / 1000 <= p <= 10 / 1000 for p in prices.values()), actor_dir.name
            assert list(prices.values()) == sorted(prices.values(), reverse=True), actor_dir.name  # higher tiers pay less
