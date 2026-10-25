import httpx
import pytest

from factory.common.config import load_config
from factory.scout.report import render_issue_body
from factory.scout.run import ScoutResult, run_scout
from factory.scout.sources import FixtureSource


@pytest.fixture
def source(fixtures_dir):
    return FixtureSource(fixtures_dir)


def test_selects_ranked_candidates_for_validation(source, config, as_of):
    result = run_scout(source, config, as_of)
    # Up to candidates_to_validate (40); the sample data has 33 niches above the minimum demand.
    assert len(result.candidates) == 33
    assert [c.rank for c in result.candidates] == list(range(1, 34))
    scores = [c.score for c in result.candidates]
    assert scores == sorted(scores, reverse=True)
    assert result.store_queries == 1 + len(config["scout"]["store"]["categories"])
    assert result.actors_seen == 84  # merged across overlapping category queries
    assert result.ideas_parsed == 6 and result.ideas_open == 6


def test_every_candidate_has_the_required_numbers(source, config, as_of):
    for c in run_scout(source, config, as_of).candidates:
        assert c.users_7d <= c.users_30d <= c.users_90d
        if c.leader:
            assert c.leader.failure_rate is not None
            assert c.leader.price_label
            assert c.leader.days_since_update is not None
        else:
            assert c.open_idea_upvotes > 0


def test_niches_that_can_never_pass_are_excluded(source, config, as_of):
    result = run_scout(source, config, as_of)
    ids = {c.niche_id for c in result.candidates}
    assert not ids & {"linkedin-job", "youtube-channel", "google-map", "instagram-profile", "website-content"}
    assert result.niches_excluded == 5


def test_platform_niches_are_excluded(source, config, as_of):
    # conftest turns the platform list off for the sample data; turn the real one back on.
    config["scout"]["exclude"]["platforms"] = load_config()["scout"]["exclude"]["platforms"]
    result = run_scout(source, config, as_of)
    assert not any(k in ("google", "amazon", "trustpilot") for c in result.candidates for k in c.keywords)
    assert result.niches_excluded > 5


def test_recently_blocked_niches_are_skipped(source, config, as_of):
    blocked = {"product-hunt": {"reason": "needs a login", "since": "2026-10-18"}, "gone": {"reason": "x", "since": "x"}}
    result = run_scout(source, config, as_of, blocked)
    assert "product-hunt" not in {c.niche_id for c in result.candidates}
    assert result.niches_blocked == 1
    assert result.blocked_niches == blocked  # carried forward for the Validator to write back
    assert "1 skipped after failing Legality in recent weeks" in render_issue_body(result, config)


def test_inconsistent_pool_sizes_are_rejected(source, config, as_of):
    config["scout"]["details"]["niche_pool"] = 10
    with pytest.raises(ValueError, match="candidates_to_validate"):
        run_scout(source, config, as_of)


def test_details_are_fetched_only_for_the_pool(source, config, as_of):
    config["scout"]["candidates_per_week"] = 5
    config["scout"]["candidates_to_validate"] = 5
    config["scout"]["details"]["niche_pool"] = 5
    config["scout"]["details"]["actors_per_niche"] = 1
    result = run_scout(source, config, as_of)
    assert result.details_fetched <= 5
    assert len(result.candidates) == 5  # only pool niches are ranked in the final pass


def test_missing_detail_is_reported(source, config, as_of):
    result = run_scout(source, config, as_of)
    assert "1 Actor detail lookup failed; that Actor counts as maintained." in result.warnings
    shopify = next(c for c in result.candidates if c.niche_id == "shopify-product")
    assert shopify.maintained_unknown == 1


def test_niches_with_your_own_actor_are_skipped(source, config, as_of):
    config["owner"]["apify_username"] = "basalt-api"  # owns the Greenhouse leader in the fixtures
    result = run_scout(source, config, as_of)
    assert "greenhouse-job" in result.skipped_own_niches
    assert all(c.niche_id != "greenhouse-job" for c in result.candidates)


def test_round_trips_through_json(source, config, as_of):
    result = run_scout(source, config, as_of)
    again = ScoutResult.from_dict(result.to_dict())
    assert again.to_dict() == result.to_dict()


class FlakySource(FixtureSource):
    def __init__(self, fixtures_dir, fail_categories):
        super().__init__(fixtures_dir)
        self.fail_categories = fail_categories

    def store_page(self, *, category, offset, limit, sort_by):
        if category in self.fail_categories:
            raise httpx.ConnectError("blocked")
        return super().store_page(category=category, offset=offset, limit=limit, sort_by=sort_by)

    def ideas_export(self):
        raise httpx.ConnectError("blocked")


def test_a_failed_query_becomes_a_warning(fixtures_dir, config, as_of):
    result = run_scout(FlakySource(fixtures_dir, {"JOBS"}), config, as_of)
    assert any("category=JOBS" in w for w in result.warnings)
    assert any("Ideas export could not be fetched" in w for w in result.warnings)
    assert len(result.candidates) >= config["scout"]["candidates_per_week"]


def test_every_query_failing_is_an_error(fixtures_dir, config, as_of):
    every = {None, *config["scout"]["store"]["categories"]}
    with pytest.raises(RuntimeError, match="Every Store query failed"):
        run_scout(FlakySource(fixtures_dir, every), config, as_of)


def test_unquoted_stopwords_are_rejected(source, config, as_of):
    config["scout"]["clustering"]["stopwords"].append(False)
    with pytest.raises(ValueError, match="quoted strings"):
        run_scout(source, config, as_of)


def test_pagination_advances_by_limit(fixtures_dir, config, as_of):
    config["scout"]["store"]["page_size"] = 10
    config["scout"]["store"]["max_items_per_query"] = 30
    source = FixtureSource(fixtures_dir)
    run_scout(source, config, as_of)
    offsets = [args[1] for kind, args in source.requests if kind == "store" and args[0] is None]
    assert offsets == [0, 10, 20]
