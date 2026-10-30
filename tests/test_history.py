"""Scout's memory of hard Legality failures (Q18)."""

import json
from datetime import datetime, timezone

from factory.scout.history import active, hard_fails, load_blocked, load_history, parse_hard_fails
from factory.validator.brief import ASSESSED_MARKER, DATA_MARKER, HARD_FAILS_MARKER, _hidden_json

NOW = datetime(2026, 11, 1, 5, 17, tzinfo=timezone.utc)


def record(niche_id, status, reason):
    return {"niche_id": niche_id, "checks": [{"name": "demand", "status": "pass", "reason": ""},
                                             {"name": "legality", "status": status, "reason": reason}]}


RECORDS = [
    record("google-trend", "fail", "terms unclear; robots.txt disallows /trends on trends.google.com"),
    record("semrush-seo", "fail", "needs a login; terms forbid automated access or reuse"),
    record("greenhouse-job", "fail", "the source mixes in personal data; terms unclear"),  # not hard
    record("sitemap", "unknown", "terms unclear; no public URL to check"),
    record("sec-edgar-filing", "pass", "official API, no login, no personal data, terms allow it"),
]


class StubGitHub:
    def __init__(self, issues, comments):
        self.issues, self.comments, self.since = issues, comments, None

    def list_issues(self, label, since):
        self.since = since
        return self.issues

    def list_comments(self, number):
        return self.comments.get(number, [])


def test_only_hard_reasons_count():
    assert hard_fails(RECORDS, "2026-10-25") == {
        "google-trend": {"reason": "robots.txt disallows /trends on trends.google.com", "since": "2026-10-25"},
        "semrush-seo": {"reason": "needs a login", "since": "2026-10-25"},
    }


def test_entries_expire_after_the_configured_weeks():
    blocked = {"old": {"reason": "needs a login", "since": "2026-08-01"},
               "new": {"reason": "needs a login", "since": "2026-10-25"}}
    assert set(active(blocked, NOW, 12)) == {"new"}


def test_reads_the_hard_fails_list_and_older_briefs():
    carried = {"amazon-product": {"reason": "terms forbid automated access or reuse", "since": "2026-09-06"}}
    issues = [
        {"number": 9, "title": "Scout 2026-W44: 20 candidate niches", "created_at": "2026-11-01T05:20:00Z"},
        {"number": 8, "title": "Scout 2026-W43: 20 candidate niches", "created_at": "2026-10-25T07:58:00Z"},
        {"number": 5, "title": "Builder rehearsal: sample data", "created_at": "2026-10-24T23:26:50Z"},
    ]
    comments = {
        9: [{"body": "brief" + _hidden_json(HARD_FAILS_MARKER, carried)}],
        8: [{"body": "older brief <!-- " + DATA_MARKER + " " + _hidden_data_from(RECORDS) + " -->"}],
        5: [{"body": "<!-- " + DATA_MARKER + " " + _hidden_data_from([record("zz", "fail", "needs a login")]) + " -->"}],
    }
    github = StubGitHub(issues, comments)
    blocked = load_blocked(github, "scout", NOW, 12)
    assert set(blocked) == {"amazon-product", "google-trend", "semrush-seo"}  # not the rehearsal's "zz"
    assert blocked["semrush-seo"]["since"] == "2026-10-25"
    assert github.since.startswith("2026-08-09")


def test_niches_assessed_in_recent_issues_are_remembered():
    issues = [
        {"number": 11, "title": "Scout 2026-10-28: 20 candidate niches", "created_at": "2026-10-28T05:20:00Z"},
        {"number": 8, "title": "Scout 2026-W43: 20 candidate niches", "created_at": "2026-09-27T07:58:00Z"},
        {"number": 5, "title": "Builder rehearsal: sample data", "created_at": "2026-10-30T23:26:50Z"},
    ]
    blocked_list = {"semrush-seo": {"reason": "needs a login", "since": "2026-10-28"}}
    comments = {
        11: [{"body": "brief" + _hidden_json(HARD_FAILS_MARKER, blocked_list) + _hidden_json(ASSESSED_MARKER, ["kalshi", "semrush-seo"])}],
        8: [{"body": "brief" + _hidden_json(ASSESSED_MARKER, ["too-old"])}],  # 35 days before NOW
        5: [{"body": "brief" + _hidden_json(ASSESSED_MARKER, ["rehearsal"])}],
    }
    blocked, recent = load_history(StubGitHub(issues, comments), "scout", NOW, 12, 28)
    assert set(blocked) == {"semrush-seo"} and recent == {"kalshi", "semrush-seo"}
    # A brief from before Q20 has no assessed list: the candidates in its hidden data count instead.
    issues[1]["created_at"] = "2026-10-25T07:58:00Z"
    comments[8] = [{"body": "older brief <!-- " + DATA_MARKER + " " + _hidden_data_from(RECORDS[:2]) + " -->"}]
    recent = load_history(StubGitHub(issues, comments), "scout", NOW, 12, 28)[1]
    assert recent == {"kalshi", "semrush-seo", "google-trend"}
    assert load_history(StubGitHub(issues, comments), "scout", NOW, 12, 0)[1] == set()


def test_unreadable_data_is_skipped():
    issues = [{"number": 8, "title": "Scout 2026-W43", "created_at": "2026-10-25T07:58:00Z"}]
    github = StubGitHub(issues, {8: [{"body": f"<!-- {HARD_FAILS_MARKER} not json -->"}]})
    assert load_blocked(github, "scout", NOW, 12) == {}


def test_hidden_list_round_trips_with_angle_brackets():
    blocked = {"x": {"reason": "robots.txt disallows /a>b on x.com", "since": "2026-10-25"}}
    text = _hidden_json(HARD_FAILS_MARKER, blocked)
    assert ">b" not in text.removesuffix(" -->")
    assert parse_hard_fails("brief\n" + text + "\n") == blocked


def _hidden_data_from(records):
    return json.dumps(records).replace(">", "\\u003e")
