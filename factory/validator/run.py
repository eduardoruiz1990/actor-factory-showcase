"""Validator pipeline: assess each candidate, check robots.txt, apply the five checks."""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from factory.scout.models import Candidate
from factory.validator.assessment import Assessment, AssessmentError, Assessor
from factory.validator.checks import PASS, CheckResult, evaluate
from factory.validator.robots import RobotsChecker, RobotsResult

log = logging.getLogger(__name__)


@dataclass
class Validation:
    candidate: Candidate
    checks: list[CheckResult]
    assessment: Assessment | None
    assessment_error: str | None
    robots: RobotsResult | None

    @property
    def passed(self) -> int:
        return sum(1 for check in self.checks if check.status == PASS)

    @property
    def verdict(self) -> str:
        return "PASS" if self.passed == len(self.checks) else "FAIL"

    def check(self, name: str) -> CheckResult:
        return next(c for c in self.checks if c.name == name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "niche_id": self.candidate.niche_id,
            "rank": self.candidate.rank,
            "label": self.candidate.label,
            "verdict": self.verdict,
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
            "assessment": self.assessment.to_dict() if self.assessment else None,
            "assessment_error": self.assessment_error,
            "robots": self.robots.to_dict() if self.robots else None,
        }


def rank_for_issue(validations: list[Validation]) -> list[Validation]:
    """Order all validations for the issue and renumber their ranks from 1.

    Candidates passing all five checks come first, then by checks passed, then by Scout's order.
    """
    ordered = sorted(validations, key=lambda v: (v.verdict != "PASS", -v.passed, v.candidate.rank))
    for position, validation in enumerate(ordered, start=1):
        validation.candidate.rank = position
    return ordered


def validate(
    candidates: list[Candidate], assessor: Assessor, robots: RobotsChecker, config: dict[str, Any]
) -> list[Validation]:
    # Claude assessments run in parallel; robots.txt fetches stay sequential so the polite rate limit holds.
    workers = max(1, int(config["validator"].get("concurrency", 1)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(lambda c: _assess(assessor, c), candidates))

    results = []
    for candidate, (assessment, error) in zip(candidates, outcomes):
        robots_result = robots.check(assessment.sample_urls, assessment.target_domain) if assessment else None
        checks = evaluate(candidate, assessment, robots_result, config)
        if error:
            # Show why the model-based checks are unknown.
            checks = [
                CheckResult(c.name, c.status, f"assessment failed: {error}") if c.reason == "no assessment" else c
                for c in checks
            ]
        results.append(Validation(candidate, checks, assessment, error, robots_result))
    return results


def _assess(assessor: Assessor, candidate: Candidate) -> tuple[Assessment | None, str | None]:
    try:
        return assessor.assess(candidate), None
    except AssessmentError as exc:
        log.warning("%s: %s", candidate.niche_id, exc)
        return None, str(exc)
