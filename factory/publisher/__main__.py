"""Publisher CLI, run by .github/workflows/publish.yml after a merge to main.

    python -m factory.publisher changed --before <sha> --after <sha>   # print changed Actor names
    python -m factory.publisher listing <name> [--build-url URL]       # open or update its publish issue

The listing step sets the Actor's Store listing (title, description, SEO text,
categories) from actor.json and listing.json through the Apify API; `apify push`
does not. Then it asks whether the Actor is already public. If it is, nothing is
opened: the push was an update. Otherwise it opens (or updates) the issue
"Publish <name>" with the listing text and pricing to enter.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from factory.common.config import REPO_ROOT, load_config
from factory.common.github import GitHubClient
from factory.common.http import PoliteClient
from factory.publisher.listing import changed_actors, load_actor, render_listing, store_fields


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m factory.publisher")
    sub = parser.add_subparsers(dest="command", required=True)
    changed = sub.add_parser("changed")
    changed.add_argument("--before", required=True)
    changed.add_argument("--after", required=True)
    listing = sub.add_parser("listing")
    listing.add_argument("name")
    listing.add_argument("--build-url")
    listing.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config")
    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "changed":
        diff = subprocess.run(["git", "diff", "--name-only", args.before, args.after],
                              capture_output=True, text=True, check=True)
        for name in changed_actors(diff.stdout.splitlines(), REPO_ROOT):
            print(name)
        return 0

    owner = config["owner"]["apify_username"]
    data = load_actor(REPO_ROOT / "actors" / args.name)
    body = render_listing(args.name, owner, data, args.build_url)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        Path(summary).open("a", encoding="utf-8").write(body + "\n")
    if args.dry_run:
        print(body)
        return 0

    with PoliteClient.from_config(config) as http:
        token = os.environ.get("APIFY_TOKEN", "")
        url = f"{config['apify']['api_base']}/acts/{owner}~{args.name}"
        fields, unknown = store_fields(data, config["scout"]["store"]["categories"])
        for category in unknown:
            print(f"::warning title=Publisher::{args.name}: {category} is not an Apify Store category; left out")
        sync_listing(http, url, token, fields)
        detail = http.get(url, headers={"Authorization": f"Bearer {token}"})
        if detail.status_code == 200 and (detail.json().get("data") or {}).get("isPublic"):
            print(f"{args.name} is already public; no publish issue needed.")
            return 0
        github = GitHubClient.from_env(http)
        label = config["publisher"]["publish_label"]
        github.ensure_label(label, "0e8a16", "Actors waiting for you to publish in Apify Console")
        title = f"Publish {args.name}"
        existing = github.find_open_issue(title, label)
        issue = github.update_issue(existing["number"], body=body) if existing else github.create_issue(title, body, [label])
        print(f"Publish issue #{issue['number']}: {issue['html_url']}")
    return 0


def sync_listing(http: PoliteClient, url: str, token: str, fields: dict) -> bool:
    """Set the Store listing fields; only the fields sent change. A failure is a warning: the deploy itself worked."""
    if not fields:
        return False
    response = http.request("PUT", url, json=fields, headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200:
        print(f"::warning title=Publisher::Store listing not updated (HTTP {response.status_code}): "
              f"{response.text[:200]}")
        return False
    print(f"Store listing updated: {', '.join(sorted(fields))}")
    return True


if __name__ == "__main__":
    sys.exit(main())
