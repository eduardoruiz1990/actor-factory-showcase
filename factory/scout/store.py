"""Parse Apify Store API items and Actor details into ActorRecords.

Field names follow Apify's OpenAPI spec (apify/apify-docs, apify-api/openapi):
StoreActor, ActorStats, CurrentPricingInfo and the ActorRunPricingInfo variants.
Parsing is tolerant: a missing field leaves the default rather than failing.
"""

import re
from typing import Any

from factory.scout.models import ActorRecord

# PAY_PER_EVENT events that charge per result, when no event is marked primary.
PER_RESULT_EVENT = re.compile(
    r"(result|item|record|row|listing|product|review|post|profile|page|job|filing|dataset)", re.I
)


def parse_store_item(item: dict[str, Any], failure_statuses: list[str]) -> ActorRecord:
    stats = item.get("stats") or {}
    runs = stats.get("publicActorRunStats30Days") or {}
    rating = item.get("actorReviewRating", stats.get("actorReviewRating"))
    count = item.get("actorReviewCount", stats.get("actorReviewCount"))
    review_count = int(count or 0)
    model, price, label = price_per_1000(item.get("currentPricingInfo") or {})
    username = item.get("username", "")
    name = item.get("name", "")
    return ActorRecord(
        id=item.get("id") or f"{username}~{name}",
        username=username,
        name=name,
        title=item.get("title") or name,
        url=item.get("url") or f"https://apify.com/{username}/{name}",
        description=(item.get("description") or "")[:300],
        categories=list(item.get("categories") or []),
        users_7d=int(stats.get("totalUsers7Days") or 0),
        users_30d=int(stats.get("totalUsers30Days") or 0),
        users_90d=int(stats.get("totalUsers90Days") or 0),
        runs_30d_total=int(runs.get("TOTAL") or 0),
        runs_30d_failed=sum(int(runs.get(status) or 0) for status in failure_statuses),
        # Apify reports 0 for an Actor nobody has reviewed: that is "unrated", not "rated 0".
        rating=float(rating) if rating and (count is None or review_count > 0) else None,
        review_count=review_count,
        notice=item.get("notice"),
        pricing_model=model,
        price_per_1000_usd=price,
        price_label=label,
    )


def apply_actor_detail(record: ActorRecord, detail: dict[str, Any], failure_statuses: list[str]) -> None:
    """Fill in what only GET /v2/acts/{actorId} knows: build date, deprecation, pricing.

    Run stats and ratings are taken from the detail too when the Store item lacked them.
    """
    builds = detail.get("taggedBuilds") or {}
    latest = builds.get("latest") or {}
    record.last_build_at = latest.get("finishedAt") or detail.get("modifiedAt") or record.last_build_at
    record.is_deprecated = bool(detail.get("isDeprecated"))
    if detail.get("notice") is not None:
        record.notice = detail["notice"]
    stats = detail.get("stats") or {}
    runs = stats.get("publicActorRunStats30Days") or {}
    if record.runs_30d_total == 0 and runs.get("TOTAL"):
        record.runs_30d_total = int(runs["TOTAL"])
        record.runs_30d_failed = sum(int(runs.get(status) or 0) for status in failure_statuses)
    if record.rating is None and stats.get("actorReviewRating") and stats.get("actorReviewCount"):
        record.rating = float(stats["actorReviewRating"])
        record.review_count = int(stats["actorReviewCount"])
    if record.price_per_1000_usd is None and record.pricing_model not in ("FREE", "FLAT_PRICE_PER_MONTH"):
        infos = sorted(detail.get("pricingInfos") or [], key=lambda p: p.get("startedAt") or "")
        if infos:
            record.pricing_model, record.price_per_1000_usd, record.price_label = price_per_1000(infos[-1])


def price_per_1000(info: dict[str, Any]) -> tuple[str, float | None, str]:
    """Return (pricing model, USD per 1,000 results or None, human label)."""
    model = info.get("pricingModel") or "UNKNOWN"
    if model == "FREE":
        return model, 0.0, "Free"
    if model == "PRICE_PER_DATASET_ITEM":
        unit = _unit_price(info.get("pricePerUnitUsd"), info.get("tieredPricing"), "tieredPricePerUnitUsd")
        if unit is None:
            return model, None, "Per result (price unknown)"
        return model, unit * 1000, f"{_usd(unit * 1000)} / 1,000 results"
    if model == "PAY_PER_EVENT":
        events = ((info.get("pricingPerEvent") or {}).get("actorChargeEvents")) or {}
        event = _per_result_event(events)
        if event is None:
            return model, None, "Pay per event (no per-result event)"
        unit = _unit_price(event.get("eventPriceUsd"), event.get("eventTieredPricingUsd"), "tieredEventPriceUsd")
        if unit is None:
            return model, None, "Pay per event (price unknown)"
        return model, unit * 1000, f"{_usd(unit * 1000)} / 1,000 results (per event)"
    if model == "FLAT_PRICE_PER_MONTH":
        monthly = info.get("pricePerUnitUsd")
        return model, None, f"{_usd(monthly)} / month (rental)" if monthly else "Rental"
    return model, None, "unknown"


def _per_result_event(events: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    repeatable = {name: e for name, e in events.items() if not e.get("isOneTimeEvent")}
    for event in repeatable.values():
        if event.get("isPrimaryEvent"):
            return event
    for name, event in repeatable.items():
        if PER_RESULT_EVENT.search(name) or PER_RESULT_EVENT.search(event.get("eventTitle") or ""):
            return event
    return None


def _unit_price(flat: Any, tiers: dict[str, dict[str, Any]] | None, tier_key: str) -> float | None:
    if isinstance(flat, (int, float)):
        return float(flat)
    if tiers:
        # The FREE tier is the list price most buyers see; otherwise take the highest tier price.
        if "FREE" in tiers and isinstance(tiers["FREE"].get(tier_key), (int, float)):
            return float(tiers["FREE"][tier_key])
        prices = [t.get(tier_key) for t in tiers.values() if isinstance(t.get(tier_key), (int, float))]
        if prices:
            return float(max(prices))
    return None


def _usd(amount: float) -> str:
    return f"${amount:,.2f}" if amount >= 0.1 else f"${amount:,.4f}"
