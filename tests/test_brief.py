import pytest

from factory.scout.run import run_scout
from factory.scout.sources import FixtureSource
from factory.validator.assessment import FixtureAssessor
from factory.validator.brief import BRIEF_MARKER, MAX_BODY_CHARS, parse_hidden_data, render_brief, verdict_labels
from factory.validator.robots import RobotsChecker, fixture_fetcher
from factory.validator.run import rank_for_issue, validate

ASSESSED = 33


@pytest.fixture
def validations(fixtures_dir, config, as_of):
    """The 20 candidates the issue lists, as the Validator CLI picks them."""
    result = run_scout(FixtureSource(fixtures_dir), config, as_of)
    assessor = FixtureAssessor(fixtures_dir / "validator" / "assessments.json")
    ranked = rank_for_issue(validate(result.candidates, assessor, RobotsChecker(fixture_fetcher(fixtures_dir / "robots")), config))
    assert len(ranked) == ASSESSED
    return ranked[: config["scout"]["candidates_per_week"]]


def visible(brief):
    return brief[: brief.index("<!-- factory:validator-data")]


def test_brief_scores_every_candidate(validations, config):
    brief = render_brief(validations, config, "2026-W43", assessed=ASSESSED)
    assert brief.startswith(BRIEF_MARKER)
    rows = [l for l in brief.splitlines() if l.startswith("| ") and not l.startswith("| #")]
    assert len(rows) == 20
    assert ("**6 of 20 listed candidates pass all five checks, 1 needs your review of its terms** "
            "(33 assessed; the issue lists the best 20).") in brief
    assert "`claude-sonnet-5-5`" in brief


def test_brief_is_about_one_page(validations, config):
    text = visible(render_brief(validations, config, "2026-W43", assessed=ASSESSED))
    # 20 table rows + 3 detailed picks (about 12 lines each) + one reason line per other candidate + headings.
    assert len(text.splitlines()) <= 100
    assert len(text) < 12_000


def test_best_picks_follow_scout_rank_and_list_reasons(validations, config):
    brief = render_brief(validations, config, "2026-W43", assessed=ASSESSED)
    picks = brief[brief.index("### Best picks"):brief.index("### Why the others")]
    assert picks.index("#1 SEC EDGAR") < picks.index("#2 Greenhouse") < picks.index("#3 TED")
    assert "Also passing: #4 npm Package Downloads Scraper, #5 Lever Jobs Scraper, #6 Federal grant" in picks
    others = brief[brief.index("### Why the others"):]
    assert "**#8 Product Hunt Scraper** — Legality: needs a login" in others


def test_no_passing_candidates(validations, config):
    for v in validations:
        v.checks[0].status = "fail"
    assert "None this week" in render_brief(validations, config, "2026-W43", assessed=ASSESSED)


def test_hidden_data_round_trips(validations, config):
    data = parse_hidden_data(render_brief(validations, config, "2026-W43", assessed=ASSESSED))
    assert len(data) == 20
    assert {d["verdict"] for d in data} == {"PASS", "REVIEW", "FAIL"}
    assert data[0]["assessment"]["proposed_actor_name"]


def test_size_guard_drops_assessments_then_all_hidden_data(validations, config, monkeypatch):
    from factory.validator.brief import _hidden_data

    full = render_brief(validations, config, "2026-W43", assessed=ASSESSED)
    slim = len(visible(full)) + len(_hidden_data(validations, with_assessments=False)) + 10
    monkeypatch.setattr("factory.validator.brief.MAX_BODY_CHARS", slim)
    data = parse_hidden_data(render_brief(validations, config, "2026-W43", assessed=ASSESSED))
    assert data and all(d["assessment"] is None for d in data)
    monkeypatch.setattr("factory.validator.brief.MAX_BODY_CHARS", 1_000)
    brief = render_brief(validations, config, "2026-W43", assessed=ASSESSED)
    assert parse_hidden_data(brief) is None and "### Best picks" in brief
    assert MAX_BODY_CHARS < 65_536


def test_verdict_labels(validations):
    labels = verdict_labels(validations)
    assert labels["greenhouse-job"] == "5/5 ✅ PASS"
    assert labels["trustpilot-review"].endswith("❌")


def test_review_candidates_get_their_own_section_and_build_command(validations, config):
    brief = render_brief(validations, config, "2026-W43", assessed=ASSESSED)
    section = brief[brief.index("### 🔎 Needs your review"):brief.index("### Why the others")]
    assert "**#7 Shopify Products Scraper** (example-store.myshopify.com)" in section
    assert "`/build shopify-product terms-reviewed`" in section
    assert "| 7 | Shopify Products Scraper | ✅ | ✅ | ❔ | ✅ | ✅ | 🔎 **REVIEW** |" in brief
    assert verdict_labels(validations)["shopify-product"] == "4/5 🔎 REVIEW"
