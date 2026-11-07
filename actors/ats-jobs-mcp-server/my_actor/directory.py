"""Search without naming companies (QUESTIONS Q29): a small daily index picks the boards, which are then read live.

.github/workflows/directory.yml stores the index in a named Apify store that anyone with its ID can read, so a
user's run needs no token for it. It holds board names, job titles and locations only. A run reads only the
boards with a matching job, most matches first, so the jobs it returns are live; the index can miss at most
about a day of new jobs.
"""

from __future__ import annotations

import gzip
import json
from typing import Any

from . import source
from .polite import PoliteClient

STORE_ID = 'iorpIauYh7aGMjuLy'
INDEX_URL = f'https://api.apify.com/v2/key-value-stores/{STORE_ID}/records/index.json.gz'


class DirectoryUnavailable(Exception):
    pass


async def load(http: PoliteClient) -> dict[str, Any]:
    """The index, or DirectoryUnavailable with a message fit to show the user."""
    try:
        response = await http.get(INDEX_URL)
    except Exception as exc:
        raise DirectoryUnavailable(f'The company directory could not be read ({exc!r}). Try again later.') from exc
    if response.status_code != 200:
        raise DirectoryUnavailable(f'The company directory could not be read (HTTP {response.status_code}). '
                                   'Try again later, or name the job boards yourself.')
    # A record stored with gzip comes back unpacked by the client, or as raw bytes if the header was lost.
    body = response.content
    try:
        index = json.loads(gzip.decompress(body) if body[:2] == b'\x1f\x8b' else body)
    except (ValueError, OSError) as exc:
        raise DirectoryUnavailable('The company directory could not be read. Try again later.') from exc
    if not isinstance(index, dict) or not isinstance(index.get('boards'), dict):
        raise DirectoryUnavailable('The company directory could not be read. Try again later.')
    return index


def matching_boards(index: dict[str, Any], settings: source.Settings) -> list[str]:
    """The boards with a job matching the settings' keywords, the most matches first."""
    counts: dict[str, int] = {}
    for key, entry in index['boards'].items():
        jobs = entry.get('jobs') if isinstance(entry, dict) else None
        if not isinstance(jobs, list):
            continue
        count = sum(1 for job in jobs if isinstance(job, list) and len(job) == 2
                    and source.matches({'title': job[0], 'location': job[1]}, settings))
        if count:
            counts[key] = count
    return sorted(counts, key=lambda key: -counts[key])
