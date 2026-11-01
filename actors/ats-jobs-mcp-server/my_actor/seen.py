"""'Only new results' and 'removed results': remember what earlier runs returned.

The memory lives in a named key-value store, which survives between runs in the
user's Apify account (the default store is emptied at the start of every run).
One record per input: for each item still being returned, its key and a short
summary (SUMMARY_FIELDS), so a removed item can still be described. A key's
group is everything before its last ':' (for jobs, the board).

A run that stops early (maximum results, spending limit) keeps every earlier key
and adds the ones it pushed, so items it did not reach stay new for the next
run. Only a run that read everything forgets the items that disappeared, and
only from groups that answered: a board that failed this run keeps its items.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from apify import Actor

STORE_PREFIX = 'seen-items-'
RECORD_PREFIX = 'seen-'
SUMMARY_FIELDS = ('job_id', 'title', 'company', 'location', 'department', 'absolute_url')


def state_key(identity: Any) -> str:
    """A short, stable record name for the input that defines 'the same search' (or the user's monitor name)."""
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]


def parse_record(value: Any) -> dict[str, dict[str, Any]]:
    """The stored memory as {key: summary}; records from before removed results are a plain list of keys."""
    if isinstance(value, list):
        return {k: {} for k in value if isinstance(k, str)}
    if not isinstance(value, dict):
        return {}
    return {k: v if isinstance(v, dict) else {} for k, v in value.items() if isinstance(k, str)}


def group_of(key: str) -> str:
    return key.rpartition(':')[0]


class SeenItems:
    def __init__(self, store: Any, record: str, previous: dict[str, dict[str, Any]]) -> None:
        self._store = store
        self._record = record
        self._previous = previous
        self._fetched: set[str] = set()
        self._pushed: dict[str, dict[str, Any]] = {}
        self._unreported: set[str] = set()

    @classmethod
    async def open(cls, key: str) -> SeenItems:
        actor_id = (Actor.configuration.actor_id or 'local').lower()
        store = await Actor.open_key_value_store(name=f'{STORE_PREFIX}{actor_id}')
        record = f'{RECORD_PREFIX}{key}'
        return cls(store, record, parse_record(await store.get_value(record)))

    @property
    def skipped(self) -> int:
        """Items this run found that an earlier run already returned."""
        return len(self._fetched & self._previous.keys())

    def is_new(self, key: str) -> bool:
        self._fetched.add(key)
        return key not in self._previous

    def pushed(self, key: str, item: dict[str, Any]) -> None:
        self._pushed[key] = {field: item.get(field) for field in SUMMARY_FIELDS}

    def removed(self, read: set[str]) -> list[tuple[str, dict[str, Any]]]:
        """Items earlier runs returned that groups read in full this run no longer list, with their summaries.

        They stay in the memory until marked reported, so a run stopped by the spending limit reports them next time.
        """
        gone = [(k, s) for k, s in self._previous.items() if k not in self._fetched and group_of(k) in read]
        self._unreported = {k for k, _ in gone}
        return gone

    def reported(self, key: str) -> None:
        self._unreported.discard(key)

    async def save(self, read: set[str] | None) -> None:
        """`read`: the groups that answered in a run that read everything; None when the run stopped early."""
        if read is None:
            keep = self._previous
        else:
            keep = {k: s for k, s in self._previous.items()
                    if k in self._fetched or group_of(k) not in read or k in self._unreported}
        await self._store.set_value(self._record, keep | self._pushed)
