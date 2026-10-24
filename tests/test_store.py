import json

import pytest

from factory.scout.store import apply_actor_detail, parse_store_item, price_per_1000

FAILURES = ["FAILED", "TIMED-OUT"]


def test_parses_the_documented_openapi_example(fixtures_dir):
    page = json.loads((fixtures_dir / "apify" / "openapi_store_example.json").read_text())
    record = parse_store_item(page["data"]["items"][0], FAILURES)
    assert record.slug == "jane35/my-public-actor"
    assert (record.users_7d, record.users_30d, record.users_90d) == (2, 6, 6)
    assert record.pricing_model == "FREE"
    assert record.price_per_1000_usd == 0.0
    assert record.rating is None  # the example has no reviews
    assert record.failure_rate is None  # no publicActorRunStats30Days in the example


def test_failure_rate_counts_failed_and_timed_out_not_aborted():
    item = {
        "id": "x", "username": "u", "name": "n",
        "stats": {"publicActorRunStats30Days": {"ABORTED": 50, "FAILED": 7, "SUCCEEDED": 40, "TIMED-OUT": 3, "TOTAL": 100}},
    }
    assert parse_store_item(item, FAILURES).failure_rate == pytest.approx(0.10)


def test_zero_rating_with_no_reviews_is_unrated():
    item = {"id": "x", "username": "u", "name": "n", "actorReviewRating": 0, "actorReviewCount": 0, "stats": {}}
    assert parse_store_item(item, FAILURES).rating is None
    item.update(actorReviewRating=3.4, actorReviewCount=12)
    assert parse_store_item(item, FAILURES).rating == 3.4


@pytest.mark.parametrize(
    ("info", "expected_price", "label_part"),
    [
        ({"pricingModel": "FREE"}, 0.0, "Free"),
        ({"pricingModel": "PRICE_PER_DATASET_ITEM", "unitName": "result", "pricePerUnitUsd": 0.0025}, 2.5, "$2.50 / 1,000"),
        (
            {"pricingModel": "PRICE_PER_DATASET_ITEM", "tieredPricing": {
                "FREE": {"tieredPricePerUnitUsd": 0.004}, "GOLD": {"tieredPricePerUnitUsd": 0.002}}},
            4.0, "$4.00",
        ),
        (
            {"pricingModel": "PAY_PER_EVENT", "pricingPerEvent": {"actorChargeEvents": {
                "actor-start": {"eventTitle": "Start", "eventPriceUsd": 0.5, "isOneTimeEvent": True},
                "result": {"eventTitle": "Result", "eventPriceUsd": 0.001, "isPrimaryEvent": True}}}},
            1.0, "per event",
        ),
        (
            {"pricingModel": "PAY_PER_EVENT", "pricingPerEvent": {"actorChargeEvents": {
                "actor-start": {"eventTitle": "Start", "eventPriceUsd": 0.5, "isOneTimeEvent": True},
                "apify-default-dataset-item": {"eventTitle": "Dataset item", "eventPriceUsd": 0.002}}}},
            2.0, "per event",
        ),
        (
            {"pricingModel": "PAY_PER_EVENT", "pricingPerEvent": {"actorChargeEvents": {
                "lookup": {"eventTitle": "Lookup", "eventTieredPricingUsd": {
                    "FREE": {"tieredEventPriceUsd": 0.003}}, "isPrimaryEvent": True}}}},
            3.0, "per event",
        ),
        ({"pricingModel": "PAY_PER_EVENT", "pricingPerEvent": {"actorChargeEvents": {
            "actor-start": {"eventTitle": "Start", "eventPriceUsd": 0.5, "isOneTimeEvent": True}}}},
         None, "no per-result event"),
        ({"pricingModel": "FLAT_PRICE_PER_MONTH", "pricePerUnitUsd": 15, "trialMinutes": 1440}, None, "$15.00 / month"),
        ({}, None, "unknown"),
    ],
)
def test_price_per_1000(info, expected_price, label_part):
    _, price, label = price_per_1000(info)
    assert price == (pytest.approx(expected_price) if expected_price is not None else None)
    assert label_part in label


def test_actor_detail_supplies_build_date_and_pricing(fixtures_dir):
    detail = json.loads((fixtures_dir / "apify" / "openapi_actor_example.json").read_text())["data"]
    record = parse_store_item({"id": "x", "username": "u", "name": "n", "currentPricingInfo": {"pricingModel": "PAY_PER_EVENT"}}, FAILURES)
    detail["pricingInfos"] = [
        {"pricingModel": "PRICE_PER_DATASET_ITEM", "pricePerUnitUsd": 0.001, "startedAt": "2024-01-01T00:00:00Z"},
        {"pricingModel": "PRICE_PER_DATASET_ITEM", "pricePerUnitUsd": 0.002, "startedAt": "2025-01-01T00:00:00Z"},
    ]
    apply_actor_detail(record, detail, FAILURES)
    assert record.last_build_at == "2019-06-10T11:15:49.286Z"  # taggedBuilds.latest.finishedAt
    assert record.price_per_1000_usd == pytest.approx(2.0)  # the most recent pricing record
    assert record.is_deprecated is False


def test_detail_without_builds_falls_back_to_modified_at():
    record = parse_store_item({"id": "x", "username": "u", "name": "n"}, FAILURES)
    apply_actor_detail(record, {"modifiedAt": "2026-01-01T00:00:00Z", "isDeprecated": True}, FAILURES)
    assert record.last_build_at == "2026-01-01T00:00:00Z"
    assert record.is_deprecated is True


def test_detail_fills_run_stats_and_rating_missing_from_the_store_item():
    record = parse_store_item({"id": "x", "username": "u", "name": "n"}, FAILURES)
    detail = {"stats": {"actorReviewRating": 3.5, "actorReviewCount": 8, "publicActorRunStats30Days": {
        "FAILED": 15, "TIMED-OUT": 5, "ABORTED": 10, "SUCCEEDED": 70, "TOTAL": 100}}}
    apply_actor_detail(record, detail, FAILURES)
    assert record.failure_rate == pytest.approx(0.20)
    assert (record.rating, record.review_count) == (3.5, 8)
