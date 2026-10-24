"""Repository-level guards: config thresholds match the spec, workflows are sane, no secrets are committed."""

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_SECRETS = {
    "APIFY_TOKEN", "ANTHROPIC_API_KEY", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "DIGEST_TO",
    "GITHUB_TOKEN",
}


def test_thresholds_match_the_spec(base_config):
    v = base_config["validator"]
    assert v["model"] == "claude-sonnet-5-5"
    assert v["demand"]["min_users_30d"] == 50
    assert v["demand"]["min_idea_upvotes"] == 1
    assert v["competition"]["fewer_than_maintained_alternatives"] == 3
    assert v["competition"]["leader_failure_rate_above"] == 0.10
    assert v["competition"]["leader_rating_below"] == 4.0
    assert v["cost"]["max_share_of_price"] == 0.30
    assert base_config["scout"]["candidates_per_week"] == 20
    assert base_config["watcher"]["broken_failure_rate_24h_above"] == 0.10


def test_stopwords_are_strings(base_config):
    # A bare `no` or `on` in YAML is a boolean, which would silently stop filtering that word.
    words = base_config["scout"]["clustering"]["stopwords"]
    assert all(isinstance(w, str) for w in words)
    assert {"no", "on"} <= set(words)


def test_workflows_use_only_the_listed_secrets():
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = path.read_text()
        yaml.safe_load(text)
        used = set(re.findall(r"secrets\.([A-Z_]+)", text))
        assert used <= ALLOWED_SECRETS, f"{path.name} uses {used - ALLOWED_SECRETS}"


def test_scout_workflow_is_weekly_with_issue_permissions():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "scout.yml").read_text())
    triggers = workflow[True]  # YAML 1.1 reads the bare key "on" as True
    cron = triggers["schedule"][0]["cron"].split()
    assert cron[2:4] == ["*", "*"] and cron[4] != "*"  # one fixed weekday
    assert workflow["permissions"] == {"contents": "read", "issues": "write"}


def test_no_secrets_are_committed():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    patterns = [r"sk-ant-[A-Za-z0-9_-]{20,}", r"apify_api_[A-Za-z0-9]{20,}", r"gh[pousr]_[A-Za-z0-9]{30,}"]
    for name in files:
        path = ROOT / name
        if not path.is_file() or path.suffix in {".png", ".jpg"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            assert not re.search(pattern, text), f"possible secret in {name}"
    assert not (ROOT / ".env").exists() or ".env" not in files


def test_env_example_lists_every_secret_without_values():
    lines = (ROOT / ".env.example").read_text().splitlines()
    assigned = dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))
    assert set(assigned) == ALLOWED_SECRETS - {"GITHUB_TOKEN"}
    assert all(value == "" for value in assigned.values())
