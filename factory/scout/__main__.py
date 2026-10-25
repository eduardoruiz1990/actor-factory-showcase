"""Scout CLI.

    python -m factory.scout --fixtures tests/fixtures --dry-run   # offline, sample data
    python -m factory.scout --dry-run                             # live data, no issue
    python -m factory.scout                                       # live data, opens the weekly issue

Writes scout.json, issue_title.txt and issue_body.md to --out (and issue.json
after opening or updating the issue). Live runs also keep the raw API
responses in --out/raw for refreshing tests/fixtures.
"""

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from factory.common.config import load_config
from factory.common.github import GitHubClient, GitHubError
from factory.common.http import PoliteClient
from factory.scout.history import load_blocked
from factory.scout.report import issue_title, render_issue_body
from factory.scout.run import run_scout
from factory.scout.sources import FixtureSource, LiveSource


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m factory.scout", description=__doc__.splitlines()[0])
    parser.add_argument("--config", help="path to config.yaml")
    parser.add_argument("--fixtures", type=Path, help="read saved sample responses from this directory")
    parser.add_argument("--dry-run", action="store_true", help="write the issue body to --out; do not touch GitHub")
    parser.add_argument("--out", type=Path, default=Path("out"), help="output directory (default: out)")
    parser.add_argument("--now", help="ISO timestamp to use as 'now' (default: current UTC time)")
    parser.add_argument("--watcher-summary", type=Path, help="Markdown summary from the latest Watcher run")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = load_config(args.config)
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc).replace(microsecond=0)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    args.out.mkdir(parents=True, exist_ok=True)

    with PoliteClient.from_config(config) as http:
        if args.fixtures:
            source = FixtureSource(args.fixtures)
        else:
            source = LiveSource(
                http,
                api_base=config["apify"]["api_base"],
                ideas_url=config["apify"]["ideas_url"],
                ideas_export_url=config["apify"]["ideas_export_url"],
                apify_token=os.environ.get("APIFY_TOKEN") or None,
                raw_dir=args.out / "raw",
            )
        blocked = {} if args.fixtures else read_blocked(http, config, now)
        result = run_scout(source, config, now, blocked)

        if args.watcher_summary and args.watcher_summary.exists():
            result.watcher_summary = args.watcher_summary.read_text(encoding="utf-8")
        title = issue_title(result, config)
        body = render_issue_body(result, config)

        (args.out / "scout.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        (args.out / "issue_title.txt").write_text(title + "\n", encoding="utf-8")
        (args.out / "issue_body.md").write_text(body, encoding="utf-8")
        for warning in result.warnings:
            print(f"::warning title=Scout::{warning}")
        print(f"{title} -> {args.out / 'issue_body.md'}")

        if args.dry_run:
            return 0

        github = GitHubClient.from_env(http)
        label = config["github"]["scout_label"]
        github.ensure_label(label, "1d76db", "Weekly Scout candidate niches")
        existing = github.find_open_issue(title, label)
        if existing:
            issue = github.update_issue(existing["number"], body=body)
        else:
            issue = github.create_issue(title, body, [label])
        (args.out / "issue.json").write_text(
            json.dumps({"number": issue["number"], "url": issue["html_url"]}, indent=2), encoding="utf-8"
        )
        print(f"Issue #{issue['number']}: {issue['html_url']}")
    return 0


def read_blocked(http: PoliteClient, config: dict, now: datetime) -> dict[str, dict[str, str]]:
    """Niches to skip after a hard Legality failure in recent weekly issues (Q18); empty if GitHub is unavailable."""
    try:
        github = GitHubClient.from_env(http)
        blocked = load_blocked(github, config["github"]["scout_label"], now,
                               int(config["scout"]["history"]["skip_hard_fails_weeks"]))
    except (GitHubError, httpx.HTTPError) as exc:
        print(f"::warning title=Scout::Past Legality failures not read, so none are skipped: {exc}")
        return {}
    print(f"Skipping {len(blocked)} niches that failed Legality for a hard reason in recent weeks")
    return blocked


if __name__ == "__main__":
    raise SystemExit(main())
