"""'Only new results': remember what earlier runs returned, so a scheduled run pushes and charges only new items.

The memory lives in a named key-value store, which survives between runs in the
user's Apify account (the default store is emptied at the start of every run).
One record per input: the keys of the items that are still being returned. A
run that stops early (maximum results, spending limit) keeps every earlier key
and adds the ones it pushed, so items it did not reach stay new for the next
run. Only a run that read everything forgets the items that disappeared.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from apify import Actor

STORE_PREFIX = 'seen-items-'
RECORD_PREFIX = 'seen-'


def state_key(identity: Any) -> str:
    """A short, stable record name for the input that defines 'the same search' (or the user's monitor name)."""
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]


class SeenItems:
    def __init__(self, store: Any, record: str, previous: set[str]) -> None:
        self._store = store
        self._record = record
        self._previous = previous
        self._fetched: set[str] = set()
        self._pushed: set[str] = set()
        self.skipped = 0

    @classmethod
    async def open(cls, key: str) -> SeenItems:
        actor_id = (Actor.configuration.actor_id or 'local').lower()
        store = await Actor.open_key_value_store(name=f'{STORE_PREFIX}{actor_id}')
        record = f'{RECORD_PREFIX}{key}'
        previous = await store.get_value(record)
        return cls(store, record, {k for k in previous or [] if isinstance(k, str)})

    def is_new(self, key: str) -> bool:
        self._fetched.add(key)
        if key in self._previous:
            self.skipped += 1
            return False
        return True

    def pushed(self, key: str) -> None:
        self._pushed.add(key)

    async def save(self, complete: bool) -> None:
        """`complete`: the run read every item, so keys it no longer saw belong to items that are gone."""
        keep = self._previous & self._fetched if complete else self._previous
        await self._store.set_value(self._record, sorted(keep | self._pushed))
