"""Actor entry point: an MCP server in Standby mode, otherwise a normal run over the input's job boards.

In Standby mode (an AI agent connects to the Actor's Standby URL) the run serves
MCP requests until Apify stops it; see mcp_server.py. Any other run, including
Apify's daily test with the default input, reads the input's boards like the
jobs scraper this Actor shares its source code with.

Charging uses Apify's synthetic `apify-default-dataset-item` event: every item
pushed to the default dataset is one charged result, and push_data() stops at
the user's spending limit. With "Only new results" on, items an earlier run
with the same input already returned are skipped and not charged (seen.py).
With "Report removed results" on, a run that read every board also returns the
items earlier runs returned that are no longer listed, marked change="removed";
each is one charged result.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apify import Actor, Event

from . import directory, privacy, source
from .polite import PoliteClient
from .robots import RobotsCache
from .seen import SeenItems


async def main() -> None:
    async with Actor:
        if Actor.configuration.meta_origin == 'STANDBY':
            from .mcp_server import serve  # noqa: PLC0415 (only Standby runs need the web server)

            await serve()
            return
        Actor.on(Event.ABORTING, _on_aborting)
        actor_input = await Actor.get_input() or {}
        try:
            settings = source.Settings.from_input(actor_input)
        except ValueError as exc:
            await Actor.fail(status_message=str(exc))
            return

        try:
            pushed = await collect(settings)
        except directory.DirectoryUnavailable as exc:
            await Actor.fail(status_message=str(exc))
            return
        capped = ' Stopped at Maximum results: raise it to get every job.' if pushed >= settings.max_results else ''
        await Actor.set_status_message(f'Finished: {pushed} result(s).{capped}')


async def collect(settings: source.Settings, *, http: PoliteClient | None = None) -> int:
    """Push up to settings.max_results items; stop early at the user's spending limit."""
    client = http or PoliteClient(min_interval=1 / settings.max_requests_per_second)
    # Charge results are meaningful only under pay-per-event pricing; without it (a free Actor, or before
    # monetization is set up) the SDK reports the limit as reached even though every item is stored.
    pay_per_event = Actor.get_charging_manager().get_pricing_info().is_pay_per_event
    removed: set[str] = set()
    pushed = 0
    remember = settings.only_new or settings.report_removed
    seen = await SeenItems.open(settings.state_key) if remember else None
    read: set[str] = set()  # boards that answered this run
    complete = False
    try:
        if settings.search_directory:
            settings.board_tokens = directory.matching_boards(await directory.load(client), settings)
            Actor.log.info(f'Company directory: {len(settings.board_tokens)} boards have a matching job')
        robots = RobotsCache(client)
        async for item in source.iter_items(settings, client, robots, read):
            key = source.item_key(item)
            if seen is not None:
                new = seen.is_new(key)
                if settings.only_new and not new:
                    continue  # returned by an earlier run: not pushed, not charged
                item = {**item, 'change': 'new' if new else 'open'}
            item = privacy.clean(item, removed)
            stored, more = await _push(item, pay_per_event)
            if not stored:
                break
            pushed += 1
            if seen is not None:
                seen.pushed(key, item)
            if not more:
                break
            if pushed >= settings.max_results:
                Actor.log.warning(f'Stopped at Maximum results ({settings.max_results}): the rest of this board and '
                                  'the boards after it were not read. Raise Maximum results to get every job.')
                break
        else:
            complete = True
        if complete and seen is not None and settings.report_removed:
            for key, summary in seen.removed(read):
                stored, more = await _push(privacy.clean(_removed_item(key, summary), removed), pay_per_event)
                if stored:
                    pushed += 1
                    seen.reported(key)
                if not more:
                    break
    finally:
        if http is None:
            await client.aclose()
        if seen is not None:
            await seen.save(read if complete else None)
            if settings.only_new:
                Actor.log.info(f'Only new results: skipped {seen.skipped} returned by earlier runs.')
    if removed:
        Actor.log.info(f'Dropped personal-data fields: {", ".join(sorted(removed))}')
    return pushed


async def _push(item: dict[str, Any], pay_per_event: bool) -> tuple[bool, bool]:
    """Store and charge one result: (stored, room for more) under the user's spending limit."""
    result = await Actor.push_data(item)
    if pay_per_event and result.charged_count == 0:
        Actor.log.info('Spending limit reached; stopping.')
        return False, False  # the item was not stored: the user's spending limit is used up
    if pay_per_event and result.event_charge_limit_reached:
        Actor.log.info('Spending limit reached; stopping.')
        return True, False
    return True, True


def _removed_item(key: str, summary: dict[str, Any]) -> dict[str, Any]:
    """A result for an item that is no longer listed: its key fields and what the memory kept about it."""
    platform, board_token, job_id = key.split(':', 2)
    # summary's job_id keeps the platform's type (Greenhouse IDs are numbers); memories from before it lack one.
    return {'platform': platform, 'board_token': board_token, 'job_id': job_id, **summary, 'change': 'removed',
            'fetched_at': datetime.now(UTC).isoformat(timespec='seconds')}


async def _on_aborting(_event_data: Any) -> None:
    # Nothing to persist: results are pushed as they are produced. Exit quickly to keep the run cheap.
    await Actor.exit()
