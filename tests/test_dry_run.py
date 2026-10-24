"""Phase 1 is done when a dry run builds the weekly issue body with 20 scored candidates from sample data."""

import json

from factory.dry_run import main


def test_dry_run_builds_the_issue_with_twenty_scored_candidates(tmp_path):
    assert main(["--out", str(tmp_path)]) == 0

    body = (tmp_path / "issue_body.md").read_text(encoding="utf-8")
    header = next(line for line in body.splitlines() if line.startswith("| # "))
    assert header.endswith("Checks |")
    rows = [l for l in body.splitlines() if l.startswith("| ") and not l.startswith("| #")]
    assert len(rows) == 20
    assert all(row.rstrip(" |").split("|")[-1].strip().startswith(("5/5", "4/5", "3/5", "2/5", "1/5", "0/5")) for row in rows)

    validations = json.loads((tmp_path / "validation.json").read_text(encoding="utf-8"))
    assert len(validations) == 33  # every candidate Scout shortlisted, not only the 20 listed
    assert all(len(v["checks"]) == 5 for v in validations)
    assert all(v["assessment_error"] is None for v in validations)

    preview = (tmp_path / "issue_preview.md").read_text(encoding="utf-8")
    assert preview.startswith("# Scout 2026-W43: 20 candidate niches")
    assert "## Validator brief — week 2026-W43" in preview
