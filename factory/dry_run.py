"""Offline dry run of the weekly pipeline on the saved sample data.

    python -m factory.dry_run [--out out/dry-run]

Runs Scout and the Validator against tests/fixtures (no network, no GitHub)
and writes the weekly issue body with 20 scored candidates, the Validator
brief, and issue_preview.md (the issue as it would look with the brief below it).
"""

import argparse
import json
from pathlib import Path

from factory.common.config import REPO_ROOT
from factory.scout.__main__ import main as scout_main
from factory.validator.__main__ import main as validator_main

FIXTURES = REPO_ROOT / "tests" / "fixtures"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m factory.dry_run", description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("out/dry-run"), help="output directory (default: out/dry-run)")
    parser.add_argument("--config", help="path to config.yaml")
    args = parser.parse_args(argv)

    as_of = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["as_of"]
    common = ["--config", args.config] if args.config else []
    scout_main([*common, "--fixtures", str(FIXTURES), "--dry-run", "--out", str(args.out), "--now", as_of])
    status = validator_main(
        [*common, "--scout", str(args.out / "scout.json"), "--fixtures", str(FIXTURES), "--dry-run", "--out", str(args.out)]
    )

    body = (args.out / "issue_body.md").read_text(encoding="utf-8")
    brief = (args.out / "brief.md").read_text(encoding="utf-8")
    title = (args.out / "issue_title.txt").read_text(encoding="utf-8").strip()
    preview = f"# {title}\n\n{body}\n---\n\n_Comment from the Validator:_\n\n{brief}"
    (args.out / "issue_preview.md").write_text(preview, encoding="utf-8")
    print(f"Preview -> {args.out / 'issue_preview.md'}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
