import pytest

from factory.scout.history import parse_assessed, parse_hard_fails
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
    assert ("**8 of 20 listed candidates pass all five checks, 1 needs your review of its terms** "
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
    assert ("Also passing: #4 npm Package Downloads Scraper, #5 Lever Jobs Scraper, #6 WordPress Plugins Scraper, "
            "#7 PyPI Package Metadata Scraper, #8 Federal grant") in picks
    others = brief[brief.index("### Why the others"):]
    assert "**#10 Product Hunt Scraper** — Legality: needs a login" in others


def test_no_passing_candidates(validations, config):
    for v in validations:
        v.checks[0].status = "fail"
    assert "None this week" in render_brief(validations, config, "2026-W43", assessed=ASSESSED)


def test_hidden_data_round_trips(validations, config):
    data = parse_hidden_data(render_brief(validations, config, "2026-W43", assessed=ASSESSED))
    assert len(data) == 20
    assert {d["verdict"] for d in data} == {"PASS", "REVIEW", "FAIL"}
    assert data[0]["assessment"]["proposed_actor_name"]


def test_size_guard_drops_failing_assessments_then_all_then_the_hidden_data(validations, config, monkeypatch):
    from factory.validator.brief import BUILDABLE, NONE, _hidden_data

    full = render_brief(validations, config, "2026-W43", assessed=ASSESSED)
    buildable = len(visible(full)) + len(_hidden_data(validations, BUILDABLE)) + 10
    monkeypatch.setattr("factory.validator.brief.MAX_BODY_CHARS", buildable)
    data = parse_hidden_data(render_brief(validations, config, "2026-W43", assessed=ASSESSED))
    # The Builder still finds what it needs for every PASS and REVIEW candidate.
    assert all((d["assessment"] is not None) == (d["verdict"] in ("PASS", "REVIEW")) for d in data)
    assert any(d["verdict"] == "REVIEW" for d in data)
    bare = len(visible(full)) + len(_hidden_data(validations, NONE)) + 10
    monkeypatch.setattr("factory.validator.brief.MAX_BODY_CHARS", bare)
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
    assert "**#9 Shopify Products Scraper** (example-store.myshopify.com)" in section
    assert "`/build shopify-product terms-reviewed`" in section
    assert "| 9 | Shopify Products Scraper | ✅ | ✅ | ❔ | ✅ | ✅ | 🔎 **REVIEW** |" in brief
    assert verdict_labels(validations)["shopify-product"] == "4/5 🔎 REVIEW"


def test_assessed_niches_are_listed_and_kept_through_the_size_guard(validations, config, monkeypatch):
    ids = ["b-niche", "a-niche", "b-niche"]
    assert parse_assessed(render_brief(validations, config, "2026-11-04", assessed_ids=ids)) == ["a-niche", "b-niche"]
    monkeypatch.setattr("factory.validator.brief.MAX_BODY_CHARS", 1_000)
    assert parse_assessed(render_brief(validations, config, "2026-11-04", assessed_ids=ids)) == ["a-niche", "b-niche"]
    assert parse_assessed(render_brief(validations, config, "2026-11-04")) is None


def test_hard_fails_are_announced_and_kept_through_the_size_guard(validations, config, monkeypatch):
    blocked = {"product-hunt": {"reason": "needs a login", "since": "2026-10-25"}}
    brief = render_brief(validations, config, "2026-W43", assessed=ASSESSED, blocked=blocked, newly_blocked=1)
    assert "1 of the assessed niches failed Legality for a reason no build can fix" in brief
    assert "Scout skips them for 12 weeks" in brief
    assert parse_hard_fails(brief) == blocked
    monkeypatch.setattr("factory.validator.brief.MAX_BODY_CHARS", 1_000)
    small = render_brief(validations, config, "2026-W43", assessed=ASSESSED, blocked=blocked)
    assert parse_hidden_data(small) is None and parse_hard_fails(small) == blocked
    assert parse_hard_fails(render_brief(validations, config, "2026-W43", assessed=ASSESSED)) is None
