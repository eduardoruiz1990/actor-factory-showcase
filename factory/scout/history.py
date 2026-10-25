"""Niches that failed Legality for a reason no build can fix, read back from past weekly issues (Q18).

A niche that failed because it needs a login, its data is personal data, its
terms forbid the use, or robots.txt disallows it is skipped for
scout.history.skip_hard_fails_weeks weeks, so the Validator's slots go to
niches it has not ruled out. Each Validator brief carries the list as hidden
JSON (`factory:validator-hard-fails`): this week's hard failures plus the ones
still active, each with the date it was found.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from factory.common.github import GitHubClient
from factory.validator.brief import DATA_MARKER, HARD_FAILS_MARKER, parse_hidden_data
from factory.validator.checks import FAIL, hard_legality_fail

log = logging.getLogger(__name__)

WEEKLY_TITLE_PREFIX = "Scout "  # rehearsal and other issues with the label are ignored


def hard_fails(records: list[dict[str, Any]], since: str) -> dict[str, dict[str, str]]:
    """{niche_id: {"reason", "since"}} for Validator records whose Legality failed for a hard reason."""
    found: dict[str, dict[str, str]] = {}
    for record in records:
        legality = next((c for c in record.get("checks", []) if c.get("name") == "legality"), None)
        if not legality or legality.get("status") != FAIL:
            continue
        reason = hard_legality_fail(legality.get("reason", ""))
        if reason:
            found[record["niche_id"]] = {"reason": reason, "since": since}
    return found


def parse_hard_fails(body: str) -> dict[str, dict[str, str]] | None:
    start = body.find(f"<!-- {HARD_FAILS_MARKER} ")
    if start < 0:
        return None
    end = body.find(" -->", start)
    return json.loads(body[start + len(HARD_FAILS_MARKER) + 6 : end])


def active(blocked: dict[str, dict[str, str]], now: datetime, weeks: int) -> dict[str, dict[str, str]]:
    cutoff = (now - timedelta(weeks=weeks)).date().isoformat()
    return {nid: entry for nid, entry in blocked.items() if entry.get("since", "") >= cutoff}


def load_blocked(github: GitHubClient, label: str, now: datetime, weeks: int) -> dict[str, dict[str, str]]:
    """Hard Legality failures from the weekly issues of the last `weeks` weeks that are still active."""
    since = (now - timedelta(weeks=weeks)).isoformat()
    blocked: dict[str, dict[str, str]] = {}
    for issue in github.list_issues(label, since):
        if not issue.get("title", "").startswith(WEEKLY_TITLE_PREFIX):
            continue
        created = issue["created_at"][:10]
        for comment in github.list_comments(issue["number"]):
            body = comment.get("body") or ""
            try:
                found = parse_hard_fails(body)
                if found is None and f"<!-- {DATA_MARKER} " in body:
                    found = hard_fails(parse_hidden_data(body) or [], created)  # briefs from before Q18
            except (ValueError, KeyError, TypeError) as exc:
                log.warning("Issue #%s: unreadable Validator data (%s)", issue["number"], exc)
                continue
            for nid, entry in (found or {}).items():
                if entry.get("since", "") > blocked.get(nid, {}).get("since", ""):
                    blocked[nid] = entry
    return active(blocked, now, weeks)
