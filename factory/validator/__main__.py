"""Validator CLI.

    python -m factory.validator --scout out/scout.json --fixtures tests/fixtures --dry-run
    python -m factory.validator --scout out/scout.json            # live: Claude API, posts the brief
    python -m factory.validator --scout out/scout.json --reuse old/validation.json   # same facts, no fetching

Writes validation.json, brief.md and the updated issue_body.md (with a Checks
column) to --out. Without --dry-run it posts the brief as a comment on the
weekly issue (from --issue or --out/issue.json) and updates the issue body.
"""

import argparse
import dataclasses
import json
import logging
from datetime import datetime
from pathlib import Path

import anthropic

from factory.common.config import load_config
from factory.common.github import GitHubClient
from factory.common.http import PoliteClient
from factory.scout.history import hard_fails
from factory.scout.report import render_issue_body, week_key
from factory.scout.run import ScoutResult
from factory.validator.assessment import Assessor, ClaudeAssessor, FixtureAssessor
from factory.validator.brief import BRIEF_MARKER, render_brief, verdict_labels
from factory.validator.robots import RobotsChecker, SavedRobots, fixture_fetcher, live_fetcher
from factory.validator.run import rank_for_issue, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m factory.validator", description=__doc__.splitlines()[0])
    parser.add_argument("--config", help="path to config.yaml")
    parser.add_argument("--scout", type=Path, default=Path("out/scout.json"), help="Scout output (default: out/scout.json)")
    parser.add_argument("--fixtures", type=Path, help="use saved assessments and robots.txt files from this directory")
    parser.add_argument("--dry-run", action="store_true", help="write the brief to --out; do not touch GitHub")
    parser.add_argument("--out", type=Path, default=Path("out"), help="output directory (default: out)")
    parser.add_argument("--issue", type=int, help="weekly issue number (default: read --out/issue.json)")
    parser.add_argument("--reuse", type=Path,
                        help="validation.json of an earlier run: reuse its assessments and robots.txt results "
                             "instead of fetching them again")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = load_config(args.config)
    result = ScoutResult.from_dict(json.loads(args.scout.read_text(encoding="utf-8")))
    args.out.mkdir(parents=True, exist_ok=True)

    with PoliteClient.from_config(config) as http:
        assessor: Assessor
        if args.reuse:
            assessor = FixtureAssessor.from_validations(args.reuse)
            robots = SavedRobots(args.reuse)
        elif args.fixtures:
            assessor = FixtureAssessor(args.fixtures / "validator" / "assessments.json")
            fetch = fixture_fetcher(args.fixtures / "robots")
        else:
            # Reads ANTHROPIC_API_KEY; the SDK retries 429 and 5xx with back-off.
            assessor = ClaudeAssessor(anthropic.Anthropic(max_retries=4), config["validator"])
            fetch = live_fetcher(http)
        if not args.reuse:
            robots = RobotsChecker(fetch, config["validator"]["legality"]["robots_user_agent"])
        validations = rank_for_issue(validate(result.candidates, assessor, robots, config))
        shown = validations[: int(config["scout"]["candidates_per_week"])]

        week = week_key(datetime.fromisoformat(result.collected_at))
        new_blocked = hard_fails([v.to_dict() for v in validations], result.collected_at[:10])
        blocked = {**result.blocked_niches, **new_blocked}
        brief = render_brief(shown, config, week, assessed=len(validations), blocked=blocked,
                             newly_blocked=len(new_blocked))
        listed_result = dataclasses.replace(result, candidates=[v.candidate for v in shown])
        body = render_issue_body(listed_result, config, verdicts=verdict_labels(shown))
        (args.out / "validation.json").write_text(
            json.dumps([v.to_dict() for v in validations], indent=2), encoding="utf-8"
        )
        (args.out / "brief.md").write_text(brief, encoding="utf-8")
        (args.out / "issue_body.md").write_text(body, encoding="utf-8")

        passing = sum(1 for v in validations if v.verdict == "PASS")
        failed = [v for v in validations if v.assessment_error]
        for v in failed:
            print(f"::warning title=Validator::{v.candidate.niche_id}: {v.assessment_error}")
        print(f"{passing} of {len(validations)} candidates pass -> {args.out / 'brief.md'}")

        if not args.dry_run:
            number = args.issue or json.loads((args.out / "issue.json").read_text(encoding="utf-8"))["number"]
            github = GitHubClient.from_env(http)
            comment = github.upsert_comment(number, BRIEF_MARKER, brief)
            github.update_issue(number, body=body)
            print(f"Brief posted: {comment['html_url']}")

    # Every assessment failing means the run did not really happen (API down, quota): flag it.
    return 1 if validations and len(failed) == len(validations) else 0


if __name__ == "__main__":
    raise SystemExit(main())
