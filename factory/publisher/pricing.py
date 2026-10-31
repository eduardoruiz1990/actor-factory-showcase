"""Keep an Actor's pay-per-event price in step with `.actor/pricing.json`, only ever downwards.

Opt-in per Actor (`"managedByPublisher": true` in pricing.json). Apify applies
a price decrease immediately, but treats an increase, a new paid event or a new
pricing model as a significant change: users are notified, it starts after 14
days, it can't be cancelled and only one is allowed per month. So the Publisher
only lowers prices (or changes titles and descriptions); anything else is
refused with a warning for the owner to do in Apify Console. Prices outside
`publisher.price_per_1000_bounds` are refused too, so a typo can't multiply the
price. A rejected update is a warning; the deploy itself has already worked.

Apify keeps pricing as a history of records. The update sends the history back
unchanged plus one new record that starts now.
"""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.common.http import PoliteClient

ITEM_EVENT = "apify-default-dataset-item"
TIERS = ("FREE", "BRONZE", "SILVER", "GOLD", "PLATINUM", "DIAMOND")
# Fields the platform sets on a record; a new record leaves them out.
SERVER_FIELDS = ("createdAt", "notifiedAboutChangeAt", "notifiedAboutFutureChangeAt",
                 "notifiedAboutRentalToPpePriceChangeAt", "reasonForChange")


def load_pricing(actor_dir: Path) -> dict[str, Any]:
    return json.loads((actor_dir / ".actor" / "pricing.json").read_text(encoding="utf-8"))


def desired_tiers(event: dict[str, Any]) -> dict[str, float]:
    """Per-event price for every Apify tier, from pricePer1000Usd and the optional tiersPer1000Usd discounts."""
    base = float(event["pricePer1000Usd"]) / 1000
    tiers = {tier: float(price) / 1000 for tier, price in (event.get("tiersPer1000Usd") or {}).items()}
    prices = {"FREE": base}
    for tier in TIERS[1:]:
        # A tier without its own price inherits the one below it (Apify's console does the same for the top tiers).
        prices[tier] = round(tiers.get(tier, prices[TIERS[TIERS.index(tier) - 1]]), 8)
    return prices


def current_record(records: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    started = [r for r in records if _when(r.get("startedAt")) <= now]
    return max(started, key=lambda r: _when(r["startedAt"])) if started else None


def current_tiers(event: dict[str, Any]) -> dict[str, float]:
    tiered = event.get("eventTieredPricingUsd")
    if tiered:
        return {tier: float(tiered[tier]["tieredEventPriceUsd"]) for tier in TIERS if tier in tiered}
    return {tier: float(event["eventPriceUsd"]) for tier in TIERS}


def plan_change(pricing: dict[str, Any], records: list[dict[str, Any]], bounds: tuple[float, float],
                now: datetime) -> tuple[dict[str, Any] | None, str]:
    """The new pricing record to add, or None with the reason nothing is sent."""
    if not pricing.get("managedByPublisher"):
        return None, "pricing is managed in Apify Console (managedByPublisher is off)"
    if any(_when(r.get("startedAt")) > now for r in records):
        return None, "a scheduled pricing change is still pending"
    current = current_record(records, now)
    if current is None or current.get("pricingModel") != "PAY_PER_EVENT":
        return None, "the Actor has no pay-per-event pricing yet; set it up once in Apify Console"
    wanted = pricing["events"][ITEM_EVENT]
    tiers = desired_tiers(wanted)
    low, high = bounds
    outside = [t for t, p in tiers.items() if not low / 1000 <= p <= high / 1000]
    if outside:
        return None, f"refused: {', '.join(outside)} price outside ${low:g}-${high:g} per 1,000 (config.yaml)"
    event = current["pricingPerEvent"]["actorChargeEvents"].get(ITEM_EVENT)
    if event is None:
        return None, f"refused: adding the {ITEM_EVENT} event is a significant change; do it in Apify Console"
    old = current_tiers(event)
    raised = [t for t in TIERS if tiers[t] > old.get(t, tiers[t]) + 1e-12]
    if raised:
        return None, (f"refused: {', '.join(raised)} price would rise; increases are significant changes "
                      "(14 days' notice, once a month), so make them in Apify Console")
    same_text = event.get("eventTitle") == wanted["title"] and event.get("eventDescription") == wanted["description"]
    if same_text and "eventTieredPricingUsd" in event and all(abs(old.get(t, -1) - tiers[t]) < 1e-12 for t in TIERS):
        return None, "already up to date"
    new_event = {k: v for k, v in event.items() if k not in ("eventPriceUsd", "eventTieredPricingUsd")}
    new_event.update(eventTitle=wanted["title"], eventDescription=wanted["description"],
                     eventTieredPricingUsd={t: {"tieredEventPriceUsd": p} for t, p in tiers.items()})
    record = {k: v for k, v in copy.deepcopy(current).items() if k not in SERVER_FIELDS}
    record["pricingPerEvent"]["actorChargeEvents"][ITEM_EVENT] = new_event
    record["minimalMaxTotalChargeUsd"] = pricing.get("minimalMaxTotalChargeUsd", record.get("minimalMaxTotalChargeUsd"))
    record["startedAt"] = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return record, f"{ITEM_EVENT}: ${old['FREE'] * 1000:g} -> ${tiers['FREE'] * 1000:g} per 1,000"


def sync_pricing(http: PoliteClient, url: str, token: str, pricing: dict[str, Any], records: list[dict[str, Any]],
                 bounds: tuple[float, float], now: datetime | None = None) -> bool:
    record, reason = plan_change(pricing, records, bounds, now or datetime.now(timezone.utc))
    if record is None:
        level = "::warning title=Publisher::" if reason.startswith("refused") else ""
        print(f"{level}Pricing not changed: {reason}")
        return False
    response = http.request("PUT", url, json={"pricingInfos": [*records, record]},
                            headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200:
        print(f"::warning title=Publisher::Pricing not changed (HTTP {response.status_code}): {response.text[:300]}")
        return False
    print(f"Pricing updated: {reason}")
    return True


def _when(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
