import json

import pytest

from factory.scout.models import ActorSummary, Candidate, Idea
from factory.validator.assessment import Assessment
from factory.validator.checks import (
    FAIL, PASS, UNKNOWN, check_competition, check_cost, check_demand, check_legality, check_stability, evaluate,
    hard_legality_fail, terms_review_reason,
)
from factory.validator.robots import RobotsResult

ALLOWED = RobotsResult(True, "robots.txt allows /v1 on api.x.com")


def leader(**overrides):
    values = dict(slug="u/a", title="A", url="https://apify.com/u/a", users_30d=100, failure_rate=0.02,
                  runs_30d_total=1000, rating=4.6, review_count=20, days_since_update=10, price_per_1000_usd=2.0,
                  price_label="$2.00 / 1,000 results", pricing_model="PAY_PER_EVENT", maintained=True)
    values.update(overrides)
    return ActorSummary(**values)


def candidate(**overrides):
    values = dict(rank=1, niche_id="x", label="X", keywords=["x"], users_7d=10, users_30d=100, users_90d=200,
                  actor_count=3, maintained_alternatives=3, maintained_unknown=0, leader=leader(), alternatives=[],
                  ideas=[], open_idea_upvotes=0, weaknesses=[], demand=100, score=2.0)
    values.update(overrides)
    return Candidate(**values)


def assessment(**overrides):
    values = dict(target_site="X API", target_domain="api.x.com", sample_urls=["https://api.x.com/v1/items"],
                  data_access="official_api", login_required="no", personal_data="none", personal_data_notes="",
                  terms_allow_automated_access="yes", terms_notes="",
                  terms_source_url="https://api.x.com/terms", terms_quote="You may use the API commercially.",
                  approach="official_api",
                  compute_units_per_1000_results=0.02, proxy="none", residential_gb_per_1000_results=0.0,
                  official_api_or_feed=True, layout_change_frequency="rare", stability_notes="",
                  proposed_actor_name="x-api", pitch="p", output_fields=["a"], risks=[], confidence="high")
    values.update(overrides)
    return Assessment(**values)


# Demand: at least 50 users in 30 days across similar Actors, or an open idea with upvotes
@pytest.mark.parametrize(
    ("users", "upvotes", "status"), [(50, 0, PASS), (49, 0, FAIL), (0, 1, PASS), (10, 0, FAIL)],
)
def test_demand(config, users, upvotes, status):
    assert check_demand(candidate(users_30d=users, open_idea_upvotes=upvotes), config["validator"]["demand"]).status == status


# Competition: fewer than 3 maintained alternatives, or the leader fails over 10% of runs or is rated below 4
@pytest.mark.parametrize(
    ("maintained", "fail", "rating", "status"),
    [
        (2, 0.02, 4.6, PASS),
        (3, 0.02, 4.6, FAIL),
        (3, 0.11, 4.6, PASS),
        (3, 0.10, 4.6, FAIL),  # "over 10%"
        (3, 0.02, 3.9, PASS),
        (3, 0.02, 4.0, FAIL),  # "below 4"
        (3, 0.02, None, FAIL),  # unrated is not "rated below 4"
    ],
)
def test_competition(config, maintained, fail, rating, status):
    c = candidate(maintained_alternatives=maintained, leader=leader(failure_rate=fail, rating=rating))
    assert check_competition(c, config["validator"]["competition"]).status == status


def test_competition_without_any_actor_passes(config):
    c = candidate(maintained_alternatives=0, actor_count=0, leader=None, ideas=[Idea("i", "u", 5, "new")])
    assert check_competition(c, config["validator"]["competition"]).status == PASS


def test_legality_passes_only_when_everything_is_clear(config):
    assert check_legality(assessment(), ALLOWED, config["validator"]["legality"]).status == PASS


@pytest.mark.parametrize(
    ("overrides", "robots", "status"),
    [
        ({"login_required": "yes"}, ALLOWED, FAIL),
        ({"data_access": "requires_login", "login_required": "no"}, ALLOWED, FAIL),
        ({"login_required": "unclear"}, ALLOWED, UNKNOWN),
        ({"personal_data": "core"}, ALLOWED, FAIL),
        ({"personal_data": "removable"}, ALLOWED, PASS),  # Q6: the Actor strips it
        ({"personal_data": "unclear"}, ALLOWED, UNKNOWN),
        ({"terms_allow_automated_access": "no"}, ALLOWED, FAIL),
        ({"terms_allow_automated_access": "unclear"}, ALLOWED, UNKNOWN),
        ({}, RobotsResult(False, "robots.txt disallows /v1"), FAIL),
        ({}, RobotsResult(None, "unreachable"), UNKNOWN),
        ({}, None, UNKNOWN),
    ],
)
def test_legality_rules(config, overrides, robots, status):
    result = check_legality(assessment(**overrides), robots, config["validator"]["legality"])
    assert result.status == status


def test_login_or_personal_data_never_pass_even_if_allowed_elsewhere(config):
    cfg = dict(config["validator"]["legality"], allow_removable_personal_data=True)
    assert check_legality(assessment(personal_data="removable"), ALLOWED, cfg).status == PASS
    assert check_legality(assessment(personal_data="core"), ALLOWED, cfg).status == FAIL
    assert check_legality(assessment(login_required="yes"), ALLOWED, cfg).status == FAIL


@pytest.mark.parametrize(
    ("source", "quote"),
    [("", "You may use it."), ("https://api.x.com/terms", "  "), ("javascript:alert(1)", "You may use it."),
     ("api.x.com/terms", "You may use it.")],
)
def test_terms_yes_needs_a_cited_page_and_quote(config, source, quote):
    result = check_legality(assessment(terms_source_url=source, terms_quote=quote), ALLOWED, config["validator"]["legality"])
    assert result.status == UNKNOWN
    assert "no source page and quote" in result.reason


def test_terms_source_requirement_can_be_switched_off(config):
    cfg = dict(config["validator"]["legality"], require_terms_source=False)
    assert check_legality(assessment(terms_source_url="", terms_quote=""), ALLOWED, cfg).status == PASS


def test_legality_pass_names_the_terms_source(config):
    assert "(api.x.com)" in check_legality(assessment(), ALLOWED, config["validator"]["legality"]).reason


def test_legality_without_assessment_is_unknown(config):
    assert check_legality(None, None, config["validator"]["legality"]).status == UNKNOWN


def test_cost_uses_the_leaders_price(config):
    # 0.02 CU * $0.40 = $0.008 against 80% of $2.00
    result = check_cost(candidate(), assessment(), config["validator"]["cost"], config["apify"])
    assert result.status == PASS and "$1.60" in result.reason


def test_cost_applies_floors_and_proxy_traffic(config):
    a = assessment(approach="browser", compute_units_per_1000_results=0.1, proxy="residential",
                   residential_gb_per_1000_results=0.0)
    result = check_cost(candidate(), a, config["validator"]["cost"], config["apify"])
    # floors: 1.0 CU ($0.40) + 0.1 GB residential ($0.80) = $1.20 = 75% of $1.60
    assert result.status == FAIL
    assert "1.00 CU" in result.reason and "0.10 GB" in result.reason


@pytest.mark.parametrize(("compute_units", "status"), [(1.15, PASS), (1.25, FAIL)])
def test_cost_threshold_is_30_percent_of_the_planned_price(config, compute_units, status):
    # 1.15 CU * $0.40 = $0.46 (28.75% of $1.60); 1.25 CU = $0.50 (31.25%)
    a = assessment(approach="http", compute_units_per_1000_results=compute_units)
    assert check_cost(candidate(), a, config["validator"]["cost"], config["apify"]).status == status


def test_cost_uses_the_default_price_for_free_leaders_and_idea_niches(config):
    free = candidate(leader=leader(price_per_1000_usd=0.0))
    assert "$2.00 (default price" in check_cost(free, assessment(), config["validator"]["cost"], config["apify"]).reason
    idea = candidate(leader=None)
    assert "(default price)" in check_cost(idea, assessment(), config["validator"]["cost"], config["apify"]).reason


@pytest.mark.parametrize(
    ("official", "layout", "status"),
    [(True, "frequent", PASS), (False, "rare", PASS), (False, "occasional", FAIL), (False, "unknown", UNKNOWN)],
)
def test_stability(config, official, layout, status):
    a = assessment(official_api_or_feed=official, layout_change_frequency=layout)
    assert check_stability(a, config["validator"]["stability"]).status == status


def test_evaluate_returns_the_five_checks_in_order(config):
    names = [c.name for c in evaluate(candidate(), assessment(), ALLOWED, config)]
    assert names == ["demand", "competition", "legality", "cost", "stability"]


def test_check_results_serialise(config):
    json.dumps([c.to_dict() for c in evaluate(candidate(), None, None, config)])


UNCLEAR = dict(terms_allow_automated_access="unclear", terms_source_url="", terms_quote="", terms_notes="No reuse clause.")


def test_review_when_only_the_terms_are_unclear(config):
    cfg = config["validator"]["legality"]
    assert terms_review_reason(assessment(**UNCLEAR), ALLOWED, cfg) == "No reuse clause."
    assert terms_review_reason(assessment(terms_source_url="", terms_quote=""), ALLOWED, cfg)  # yes, but unsourced


@pytest.mark.parametrize(
    ("overrides", "robots"),
    [
        ({"terms_allow_automated_access": "no"}, ALLOWED),
        ({}, ALLOWED),  # a sourced yes passes outright; nothing to review
        ({**UNCLEAR, "login_required": "unclear"}, ALLOWED),
        ({**UNCLEAR, "personal_data": "unclear"}, ALLOWED),
        ({**UNCLEAR, "data_access": "public_html"}, ALLOWED),
        (UNCLEAR, RobotsResult(None, "unreachable")),
        (UNCLEAR, RobotsResult(False, "disallowed")),
    ],
)
def test_no_review_for_anything_but_unclear_terms(config, overrides, robots):
    assert terms_review_reason(assessment(**overrides), robots, config["validator"]["legality"]) is None


def test_removable_personal_data_follows_q6(config):
    strict = dict(config["validator"]["legality"], allow_removable_personal_data=False)
    removable = assessment(personal_data="removable")
    assert check_legality(removable, ALLOWED, strict).status == FAIL
    assert terms_review_reason(assessment(**UNCLEAR, personal_data="removable"), ALLOWED, strict) is None
    allowed = config["validator"]["legality"]
    assert check_legality(removable, ALLOWED, allowed).reason.startswith(
        "official API, no login, personal data stripped by the Actor")
    assert terms_review_reason(assessment(**UNCLEAR, personal_data="removable"), ALLOWED, allowed)


@pytest.mark.parametrize(
    ("reason", "hard"),
    [
        ("needs a login; terms unclear", "needs a login"),
        ("terms unclear; terms forbid automated access or reuse", "terms forbid automated access or reuse"),
        ("the data is personal data", "the data is personal data"),
        ("robots.txt disallows /search on x.com", "robots.txt disallows /search on x.com"),
        ("the source mixes in personal data; terms unclear", None),
        ("terms unclear; no public URL to check", None),
    ],
)
def test_hard_legality_fails(reason, hard):
    assert hard_legality_fail(reason) == hard


def test_review_can_be_switched_off(config):
    cfg = dict(config["validator"]["legality"], review_unclear_terms=False)
    assert terms_review_reason(assessment(**UNCLEAR), ALLOWED, cfg) is None
