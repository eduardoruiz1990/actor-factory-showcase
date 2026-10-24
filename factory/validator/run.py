"""Validator pipeline: assess each candidate, check robots.txt, apply the five checks."""

import logging
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


def validate(
    candidates: list[Candidate], assessor: Assessor, robots: RobotsChecker, config: dict[str, Any]
) -> list[Validation]:
    results = []
    for candidate in candidates:
        assessment, error, robots_result = None, None, None
        try:
            assessment = assessor.assess(candidate)
        except AssessmentError as exc:
            error = str(exc)
            log.warning("%s: %s", candidate.niche_id, error)
        if assessment is not None:
            robots_result = robots.check(assessment.sample_urls, assessment.target_domain)
        checks = evaluate(candidate, assessment, robots_result, config)
        if error:
            # Show why the model-based checks are unknown.
            checks = [
                CheckResult(c.name, c.status, f"assessment failed: {error}") if c.reason == "no assessment" else c
                for c in checks
            ]
        results.append(Validation(candidate, checks, assessment, error, robots_result))
    return results
