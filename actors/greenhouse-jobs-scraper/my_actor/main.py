"""Actor entry point: read input, collect results politely, push them, charge per result.

Charging uses Apify's synthetic `apify-default-dataset-item` event: every item
pushed to the default dataset is one charged result, and push_data() stops at
the user's spending limit. This file rarely needs changes; the niche lives in
source.py.
"""

from __future__ import annotations

from typing import Any

from apify import Actor, Event

from . import privacy, source
from .polite import PoliteClient
from .robots import RobotsCache


async def main() -> None:
    async with Actor:
        Actor.on(Event.ABORTING, _on_aborting)
        actor_input = await Actor.get_input() or {}
        try:
            settings = source.Settings.from_input(actor_input)
        except ValueError as exc:
            await Actor.fail(status_message=str(exc))
            return

        pushed = await collect(settings)
        await Actor.set_status_message(f'Finished: {pushed} result(s).')


async def collect(settings: source.Settings, *, http: PoliteClient | None = None) -> int:
    """Push up to settings.max_results items; stop early at the user's spending limit."""
    client = http or PoliteClient(min_interval=1 / settings.max_requests_per_second)
    # Charge results are meaningful only under pay-per-event pricing; without it (a free Actor, or before
    # monetization is set up) the SDK reports the limit as reached even though every item is stored.
    pay_per_event = Actor.get_charging_manager().get_pricing_info().is_pay_per_event
    removed: set[str] = set()
    pushed = 0
    try:
        robots = RobotsCache(client)
        async for item in source.iter_items(settings, client, robots):
            result = await Actor.push_data(privacy.clean(item, removed))
            if pay_per_event and result.charged_count == 0:
                Actor.log.info('Spending limit reached; stopping.')
                break  # the item was not stored: the user's spending limit is used up
            pushed += 1
            if pay_per_event and result.event_charge_limit_reached:
                Actor.log.info('Spending limit reached; stopping.')
                break
            if pushed >= settings.max_results:
                break
    finally:
        if http is None:
            await client.aclose()
    if removed:
        Actor.log.info(f'Dropped personal-data fields: {", ".join(sorted(removed))}')
    return pushed


async def _on_aborting(_event_data: Any) -> None:
    # Nothing to persist: results are pushed as they are produced. Exit quickly to keep the run cheap.
    await Actor.exit()
