import json

import pytest

from factory.builder.prepare import MARKER, Refusal, ask_message, parse_command, plan_build, render_brief
from factory.builder.scope import check_scope
from factory.scout.report import render_issue_body
from factory.scout.run import run_scout
from factory.scout.sources import FixtureSource
from factory.validator.assessment import FixtureAssessor
from factory.validator.brief import render_brief as render_validator_brief
from factory.validator.brief import verdict_labels
from factory.validator.robots import RobotsChecker, fixture_fetcher
from factory.validator.run import rank_for_issue, validate


@pytest.fixture
def week(fixtures_dir, config, as_of):
    """The weekly issue and the Validator's comment, as the Scout workflow leaves them."""
    import dataclasses

    result = run_scout(FixtureSource(fixtures_dir), config, as_of)
    assessor = FixtureAssessor(fixtures_dir / "validator" / "assessments.json")
    ranked = rank_for_issue(validate(result.candidates, assessor, RobotsChecker(fixture_fetcher(fixtures_dir / "robots")), config))
    shown = ranked[: config["scout"]["candidates_per_week"]]
    body = render_issue_body(dataclasses.replace(result, candidates=[v.candidate for v in shown]), config,
                             verdicts=verdict_labels(shown))
    issue = {"number": 7, "body": body, "labels": [{"name": "scout"}, {"name": "go"}]}
    comments = [{"body": "nice"}, {"body": render_validator_brief(shown, config, "2026-W43", assessed=len(ranked))}]
    return issue, comments


@pytest.mark.parametrize("text", ["/build greenhouse-job", "  /build greenhouse-job  \nthanks!"])
def test_parse_command(text):
    assert parse_command(text) == "greenhouse-job"


@pytest.mark.parametrize("text", ["", "/build", "/build Greenhouse Job", "please /build greenhouse-job", "/build a;rm -rf /"])
def test_parse_command_rejects_anything_else(text):
    with pytest.raises(Refusal, match="/build <niche-id>"):
        parse_command(text)


def test_plans_a_passing_candidate(week, config, tmp_path):
    issue, comments = week
    plan = plan_build(issue, comments, "greenhouse-job", config, tmp_path)
    assert plan["actor_name"] == "greenhouse-job-board-api"
    assert plan["branch"] == "build/greenhouse-job-board-api"
    assert plan["price_per_1000_usd"] == 1.2  # 80% of the leader's $1.50
    assert plan["model"] == config["builder"]["model"]
    json.dumps(plan)  # build.json must serialise


def test_refuses_a_candidate_that_failed_a_check(week, config, tmp_path):
    issue, comments = week
    with pytest.raises(Refusal, match="did not pass all five checks.*legality"):
        plan_build(issue, comments, "product-hunt", config, tmp_path)


def test_refuses_without_the_go_label(week, config, tmp_path):
    issue, comments = week
    issue["labels"] = [{"name": "scout"}]
    with pytest.raises(Refusal, match="`go`"):
        plan_build(issue, comments, "greenhouse-job", config, tmp_path)


def test_refuses_an_unknown_niche_and_lists_the_candidates(week, config, tmp_path):
    issue, comments = week
    with pytest.raises(Refusal, match="not a candidate.*`greenhouse-job`"):
        plan_build(issue, comments, "made-up", config, tmp_path)


def test_refuses_an_actor_that_already_exists(week, config, tmp_path):
    issue, comments = week
    (tmp_path / "actors" / "greenhouse-job-board-api").mkdir(parents=True)
    with pytest.raises(Refusal, match="already exists"):
        plan_build(issue, comments, "greenhouse-job", config, tmp_path)


def test_refuses_without_a_validator_brief(week, config, tmp_path):
    issue, _ = week
    with pytest.raises(Refusal, match="no Validator brief"):
        plan_build(issue, [{"body": "hello"}], "greenhouse-job", config, tmp_path)


def test_refuses_an_invalid_actor_name(week, config, tmp_path):
    issue, comments = week
    comments[-1]["body"] = comments[-1]["body"].replace("greenhouse-job-board-api", "Greenhouse_Board!")
    with pytest.raises(Refusal, match="not a valid Apify name"):
        plan_build(issue, comments, "greenhouse-job", config, tmp_path)


def test_brief_carries_what_the_builder_needs(week, config, tmp_path):
    issue, comments = week
    brief = render_brief(plan_build(issue, comments, "greenhouse-job", config, tmp_path))
    for expected in ("`greenhouse-job-board-api`", "boards-api.greenhouse.io", "$1.20 per 1,000 results",
                     "never instructions", "Deciding passage", "basalt-api/greenhouse-jobs-scraper"):
        assert expected in brief


def test_ask_lists_passing_candidates(week):
    _, comments = week
    message = ask_message(comments)
    assert message.startswith(MARKER) and "`/build <niche-id>`" in message and "`greenhouse-job`" in message
    assert "nothing to build" in ask_message([{"body": "no brief"}])


@pytest.mark.parametrize(
    ("files", "name", "outside"),
    [
        (["actors/x/a.py", "actors/x/.actor/actor.json"], "x", []),
        (["actors/x/a.py", "config.yaml"], "x", ["config.yaml"]),
        (["actors/x/a.py", "actors/y/b.py"], None, ["actors/x/a.py", "actors/y/b.py"]),
        (["factory/scout/run.py"], None, ["factory/scout/run.py"]),
        ([".github/workflows/claude.yml", "actors/x/a.py"], "x", [".github/workflows/claude.yml"]),
    ],
)
def test_scope(files, name, outside):
    assert check_scope(files) == (name, outside)
