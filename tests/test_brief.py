import pytest

from factory.scout.run import run_scout
from factory.scout.sources import FixtureSource
from factory.validator.assessment import FixtureAssessor
from factory.validator.brief import BRIEF_MARKER, MAX_BODY_CHARS, parse_hidden_data, render_brief, verdict_labels
from factory.validator.robots import RobotsChecker, fixture_fetcher
from factory.validator.run import validate


@pytest.fixture
def validations(fixtures_dir, config, as_of):
    result = run_scout(FixtureSource(fixtures_dir), config, as_of)
    assessor = FixtureAssessor(fixtures_dir / "validator" / "assessments.json")
    return validate(result.candidates, assessor, RobotsChecker(fixture_fetcher(fixtures_dir / "robots")), config)


def visible(brief):
    return brief[: brief.index("<!-- factory:validator-data")]


def test_brief_scores_every_candidate(validations, config):
    brief = render_brief(validations, config, "2026-W43")
    assert brief.startswith(BRIEF_MARKER)
    rows = [l for l in brief.splitlines() if l.startswith("| ") and not l.startswith("| #")]
    assert len(rows) == 20
    assert "**6 of 20 candidates pass all five checks.**" in brief
    assert "`claude-sonnet-5-5`" in brief


def test_brief_is_about_one_page(validations, config):
    text = visible(render_brief(validations, config, "2026-W43"))
    assert len(text.splitlines()) < 90
    assert len(text) < 12_000


def test_best_picks_follow_scout_rank_and_list_reasons(validations, config):
    brief = render_brief(validations, config, "2026-W43")
    picks = brief[brief.index("### Best picks"):brief.index("### Why the others")]
    assert picks.index("#4 SEC EDGAR") < picks.index("#9 Greenhouse") < picks.index("#11 TED")
    assert "Also passing: #12" in picks
    others = brief[brief.index("### Why the others"):]
    assert "**#10 Product Hunt Scraper** — Legality: needs a login" in others


def test_no_passing_candidates(validations, config):
    for v in validations:
        v.checks[0].status = "fail"
    assert "None this week" in render_brief(validations, config, "2026-W43")


def test_hidden_data_round_trips(validations, config):
    data = parse_hidden_data(render_brief(validations, config, "2026-W43"))
    assert len(data) == 20
    assert {d["verdict"] for d in data} == {"PASS", "FAIL"}
    assert data[0]["assessment"]["proposed_actor_name"]


def test_size_guard_drops_assessments(validations, config, monkeypatch):
    monkeypatch.setattr("factory.validator.brief.MAX_BODY_CHARS", 5_000)
    data = parse_hidden_data(render_brief(validations, config, "2026-W43"))
    assert all(d["assessment"] is None for d in data)
    assert MAX_BODY_CHARS < 65_536


def test_verdict_labels(validations):
    labels = verdict_labels(validations)
    assert labels["greenhouse-job"] == "5/5 ✅ PASS"
    assert labels["google-map"].endswith("❌")
