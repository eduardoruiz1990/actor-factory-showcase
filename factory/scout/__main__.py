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

from factory.common.config import load_config
from factory.common.github import GitHubClient
from factory.common.http import PoliteClient
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
                apify_token=os.environ.get("APIFY_TOKEN") or None,
                raw_dir=args.out / "raw",
            )
        result = run_scout(source, config, now)

        if args.watcher_summary and args.watcher_summary.exists():
            result.watcher_summary = args.watcher_summary.read_text(encoding="utf-8")
        title = issue_title(result)
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


if __name__ == "__main__":
    raise SystemExit(main())
