import pytest

from factory.scout.report import (
    ISSUE_MARKER, MAX_BODY_CHARS, issue_title, parse_hidden_data, render_issue_body, week_key,
)
from factory.scout.run import run_scout
from factory.scout.sources import FixtureSource


@pytest.fixture
def result(fixtures_dir, config, as_of):
    return run_scout(FixtureSource(fixtures_dir), config, as_of)


def table_rows(body):
    return [line for line in body.splitlines() if line.startswith("| ") and not line.startswith("| #")]


def test_title_and_week(result, as_of):
    assert week_key(as_of) == "2026-W43"
    assert issue_title(result) == "Scout 2026-W43: 20 candidate niches"


def test_body_lists_twenty_candidates_with_their_numbers(result, config):
    body = render_issue_body(result, config)
    assert body.startswith(ISSUE_MARKER)
    rows = table_rows(body)
    assert len(rows) == 20
    first = result.candidates[0]
    assert f"{first.users_7d:,} / {first.users_30d:,} / {first.users_90d:,}" in rows[0]
    assert f"{first.leader.failure_rate:.1%}" in rows[0]
    assert first.leader.price_label in rows[0]
    header = next(line for line in body.splitlines() if line.startswith("| # "))
    assert "Checks" not in header  # no Validator column before validation


def test_verdict_column(result, config):
    verdicts = {c.niche_id: "5/5 ✅ PASS" for c in result.candidates}
    body = render_issue_body(result, config, verdicts=verdicts)
    assert all(row.endswith("5/5 ✅ PASS |") for row in table_rows(body))


def test_hidden_data_round_trips_and_cannot_break_out(result, config):
    result.candidates[0].label = "Evil --> <script>"
    body = render_issue_body(result, config)
    data = parse_hidden_data(body)
    assert data["candidates"][0]["label"] == "Evil --> <script>"
    hidden = body[body.index("<!-- factory:scout-data"):]
    assert hidden.count("-->") == 1  # only the real end of the comment


def test_third_party_titles_cannot_break_the_table(result, config):
    result.candidates[0].label = "Jobs | [click](https://evil.example)\nnew line"
    row = table_rows(render_issue_body(result, config))[0]
    assert "[click]" not in row and "\n" not in row
    assert row.count(" | ") == table_rows(render_issue_body(result, config))[1].count(" | ")


def test_body_fits_in_a_github_issue(result, config):
    assert len(render_issue_body(result, config)) < MAX_BODY_CHARS


def test_watcher_summary_and_warnings_are_shown(result, config):
    result.watcher_summary = "All 3 Actors healthy."
    result.warnings = ["Ideas page fetched but no ideas were parsed."]
    body = render_issue_body(result, config)
    assert "All 3 Actors healthy." in body
    assert "> Ideas page fetched but no ideas were parsed." in body
