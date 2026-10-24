"""Guards on the Actor template and the Builder workflow that copies it."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "python-actor"


def test_template_has_the_official_layout_and_factory_files():
    for path in (".actor/actor.json", ".actor/input_schema.json", ".actor/dataset_schema.json", ".actor/output_schema.json",
                 ".actor/pricing.json", ".actor/listing.json", "Dockerfile", "requirements.txt", "requirements-dev.txt",
                 "README.md", "my_actor/main.py", "my_actor/source.py", "my_actor/polite.py", "my_actor/robots.py",
                 "my_actor/privacy.py", "tests/test_main.py", "tests/fetch_fixture.py"):
        assert (TEMPLATE / path).is_file(), path


def test_builder_renames_the_template_actor():
    # claude.yml sets the name with sed on this exact text.
    actor = (TEMPLATE / ".actor" / "actor.json").read_text()
    assert '"name": "my-actor"' in actor
    workflow = (ROOT / ".github" / "workflows" / "claude.yml").read_text()
    assert 's/\\"name\\": \\"my-actor\\"/\\"name\\": \\"$NAME\\"/' in workflow


def test_pricing_charges_per_result_with_the_synthetic_event():
    pricing = json.loads((TEMPLATE / ".actor" / "pricing.json").read_text())
    assert pricing["pricingModel"] == "PAY_PER_EVENT"
    result = pricing["events"]["apify-default-dataset-item"]
    assert result["isPrimary"] and result["pricePer1000Usd"] > 0
    assert [e for e in pricing["events"] if "pricePer1000Usd" in pricing["events"][e]] == ["apify-default-dataset-item"]


def test_template_pushes_through_the_privacy_guard():
    main = (TEMPLATE / "my_actor" / "main.py").read_text()
    assert "Actor.push_data(privacy.clean(item, removed))" in main


def test_builder_workflow_is_owner_only_and_never_merges():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "claude.yml").read_text())
    for job in workflow["jobs"].values():
        assert "github.repository_owner" in job["if"]
    text = (ROOT / ".github" / "workflows" / "claude.yml").read_text()
    for forbidden in ("Bash(gh pr merge:*)", "Bash(git push --force:*)", "Bash(apify push:*)"):
        assert forbidden in text.split("--disallowedTools", 1)[1]
    allowed = text.split("--allowedTools", 1)[1].split("\n", 1)[0]
    assert "gh pr merge" not in allowed and "Bash(git:*)" not in allowed and "Bash(gh:*)" not in allowed


def test_publisher_runs_only_after_merges_to_main():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "publish.yml").read_text())
    assert workflow[True]["push"]["branches"] == ["main"]
    assert "apify push --dir" in (ROOT / ".github" / "workflows" / "publish.yml").read_text()


def test_builder_is_told_to_fetch_fixtures_with_the_helper():
    assert "python -m tests.fetch_fixture" in (ROOT / "docs" / "BUILDER.md").read_text()
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "claude.yml").read_text())
    steps = workflow["jobs"]["build"]["steps"]
    assert any(s.get("id") == "claude" for s in steps)
    transcript = next(s for s in steps if s.get("name") == "Keep the build transcript")
    assert transcript["if"] == "always()"
    assert "Bash(python:*)" in str(steps)  # the helper runs under the already-allowed python
