"""Validator CLI.

    python -m factory.validator --scout out/scout.json --fixtures tests/fixtures --dry-run
    python -m factory.validator --scout out/scout.json            # live: Claude API, posts the brief

Writes validation.json, brief.md and the updated issue_body.md (with a Checks
column) to --out. Without --dry-run it posts the brief as a comment on the
weekly issue (from --issue or --out/issue.json) and updates the issue body.
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import anthropic

from factory.common.config import load_config
from factory.common.github import GitHubClient
from factory.common.http import PoliteClient
from factory.scout.report import render_issue_body, week_key
from factory.scout.run import ScoutResult
from factory.validator.assessment import Assessor, ClaudeAssessor, FixtureAssessor
from factory.validator.brief import BRIEF_MARKER, render_brief, verdict_labels
from factory.validator.robots import RobotsChecker, fixture_fetcher, live_fetcher
from factory.validator.run import validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m factory.validator", description=__doc__.splitlines()[0])
    parser.add_argument("--config", help="path to config.yaml")
    parser.add_argument("--scout", type=Path, default=Path("out/scout.json"), help="Scout output (default: out/scout.json)")
    parser.add_argument("--fixtures", type=Path, help="use saved assessments and robots.txt files from this directory")
    parser.add_argument("--dry-run", action="store_true", help="write the brief to --out; do not touch GitHub")
    parser.add_argument("--out", type=Path, default=Path("out"), help="output directory (default: out)")
    parser.add_argument("--issue", type=int, help="weekly issue number (default: read --out/issue.json)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = load_config(args.config)
    result = ScoutResult.from_dict(json.loads(args.scout.read_text(encoding="utf-8")))
    args.out.mkdir(parents=True, exist_ok=True)

    with PoliteClient.from_config(config) as http:
        assessor: Assessor
        if args.fixtures:
            assessor = FixtureAssessor(args.fixtures / "validator" / "assessments.json")
            fetch = fixture_fetcher(args.fixtures / "robots")
        else:
            # Reads ANTHROPIC_API_KEY; the SDK retries 429 and 5xx with back-off.
            assessor = ClaudeAssessor(anthropic.Anthropic(max_retries=4), config["validator"])
            fetch = live_fetcher(http)
        robots = RobotsChecker(fetch, config["validator"]["legality"]["robots_user_agent"])
        validations = validate(result.candidates, assessor, robots, config)

        week = week_key(datetime.fromisoformat(result.collected_at))
        brief = render_brief(validations, config, week)
        body = render_issue_body(result, config, verdicts=verdict_labels(validations))
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
