import pytest

from factory.scout.run import run_scout
from factory.scout.sources import FixtureSource
from factory.validator.assessment import AssessmentError, FixtureAssessor
from factory.validator.checks import CHECK_NAMES, PASS, UNKNOWN
from factory.validator.robots import RobotsChecker, fixture_fetcher
from factory.validator.run import validate


@pytest.fixture
def scout_result(fixtures_dir, config, as_of):
    return run_scout(FixtureSource(fixtures_dir), config, as_of)


def run(scout_result, fixtures_dir, config, assessor=None):
    assessor = assessor or FixtureAssessor(fixtures_dir / "validator" / "assessments.json")
    robots = RobotsChecker(fixture_fetcher(fixtures_dir / "robots"))
    return validate(scout_result.candidates, assessor, robots, config)


def test_every_candidate_gets_five_checks(scout_result, fixtures_dir, config):
    validations = run(scout_result, fixtures_dir, config)
    assert len(validations) == 20
    for v in validations:
        assert [c.name for c in v.checks] == list(CHECK_NAMES)
        assert v.assessment_error is None


def test_sample_verdicts(scout_result, fixtures_dir, config):
    verdicts = {v.candidate.niche_id: v for v in run(scout_result, fixtures_dir, config)}
    passing = {nid for nid, v in verdicts.items() if v.verdict == "PASS"}
    assert passing == {
        "sec-edgar-filing", "greenhouse-job", "ted-eu-tender", "npm-package-download", "lever-job",
        "federal-grant-opportunity-gov",
    }
    # Hard rules and robots.txt in action:
    assert verdicts["product-hunt"].check("legality").reason.startswith("needs a login")
    assert "personal data" in verdicts["trustpilot-review"].check("legality").reason
    assert "robots.txt disallows" in verdicts["google-trend"].check("legality").reason
    assert verdicts["shopify-product"].check("legality").status == UNKNOWN
    assert verdicts["google-map"].check("competition").status != PASS


class BrokenAssessor:
    def assess(self, candidate):
        raise AssessmentError("model declined to assess (category: None)")


def test_assessment_failures_leave_model_checks_unknown(scout_result, fixtures_dir, config):
    validations = run(scout_result, fixtures_dir, config, assessor=BrokenAssessor())
    for v in validations:
        assert v.verdict == "FAIL"
        for name in ("legality", "cost", "stability"):
            check = v.check(name)
            assert check.status == UNKNOWN
            assert "assessment failed: model declined" in check.reason
        assert v.check("demand").status in (PASS, "fail")  # data-only checks still run
