import pytest

from factory.scout.run import run_scout
from factory.scout.sources import FixtureSource
from factory.validator.assessment import AssessmentError, FixtureAssessor
from factory.validator.checks import CHECK_NAMES, PASS, UNKNOWN
from factory.validator.robots import RobotsChecker, fixture_fetcher
from factory.validator.run import rank_for_issue, validate


@pytest.fixture
def scout_result(fixtures_dir, config, as_of):
    return run_scout(FixtureSource(fixtures_dir), config, as_of)


def run(scout_result, fixtures_dir, config, assessor=None):
    assessor = assessor or FixtureAssessor(fixtures_dir / "validator" / "assessments.json")
    robots = RobotsChecker(fixture_fetcher(fixtures_dir / "robots"))
    return validate(scout_result.candidates, assessor, robots, config)


def test_every_candidate_gets_five_checks(scout_result, fixtures_dir, config):
    validations = run(scout_result, fixtures_dir, config)
    assert len(validations) == len(scout_result.candidates)
    for v in validations:
        assert [c.name for c in v.checks] == list(CHECK_NAMES)
        assert v.assessment_error is None


def test_sample_verdicts(scout_result, fixtures_dir, config):
    verdicts = {v.candidate.niche_id: v for v in run(scout_result, fixtures_dir, config)}
    passing = {nid for nid, v in verdicts.items() if v.verdict == "PASS"}
    assert passing == {
        "sec-edgar-filing", "greenhouse-job", "ted-eu-tender", "npm-package-download", "lever-job",
        "federal-grant-opportunity-gov",
        # Author fields only: personal data the Actor strips, allowed since Q6 was decided.
        "wordpress-plugin", "pypi-package-metadata",
    }
    # Hard rules and robots.txt in action:
    assert verdicts["product-hunt"].check("legality").reason.startswith("needs a login")
    assert "personal data" in verdicts["trustpilot-review"].check("legality").reason
    assert "robots.txt disallows" in verdicts["google-trend"].check("legality").reason
    assert verdicts["shopify-product"].check("legality").status == UNKNOWN
    assert verdicts["sitemap-url"].check("competition").status != PASS
    assert verdicts["openfda-drug-recall"].check("demand").status != PASS


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


def test_rank_for_issue_puts_passing_candidates_first(scout_result, fixtures_dir, config):
    ordered = rank_for_issue(run(scout_result, fixtures_dir, config))
    assert [v.candidate.rank for v in ordered] == list(range(1, len(ordered) + 1))
    verdicts = [v.verdict for v in ordered]
    assert verdicts[:8] == ["PASS"] * 8 and "PASS" not in verdicts[8:]
    passed = [v.passed for v in ordered[6:]]
    assert passed == sorted(passed, reverse=True)
    assert ordered[0].candidate.niche_id == "sec-edgar-filing"  # the passing candidate Scout ranked highest


class SlowAssessor(FixtureAssessor):
    """Records how many assessments overlap, to show they run in parallel."""

    def __init__(self, path):
        super().__init__(path)
        import threading
        self.lock, self.active, self.peak = threading.Lock(), 0, 0

    def assess(self, candidate):
        import time
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.02)
        with self.lock:
            self.active -= 1
        return super().assess(candidate)


def test_assessments_run_in_parallel_and_keep_their_order(scout_result, fixtures_dir, config):
    assessor = SlowAssessor(fixtures_dir / "validator" / "assessments.json")
    validations = run(scout_result, fixtures_dir, config, assessor=assessor)
    assert assessor.peak == config["validator"]["concurrency"]
    assert [v.candidate.niche_id for v in validations] == [c.niche_id for c in scout_result.candidates]
