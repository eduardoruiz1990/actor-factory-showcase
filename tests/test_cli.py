"""The live (non-dry-run) paths of the CLIs, with GitHub replaced by a recorder."""

import json

import pytest

import factory.scout.__main__ as scout_cli
import factory.validator.__main__ as validator_cli


class RecordingGitHub:
    def __init__(self):
        self.issues = {}
        self.comments = {}
        self.labels = []

    def ensure_label(self, name, color="", description=""):
        self.labels.append(name)

    def find_open_issue(self, title, label):
        return next((i for i in self.issues.values() if i["title"] == title), None)

    def create_issue(self, title, body, labels):
        number = len(self.issues) + 1
        self.issues[number] = {"number": number, "title": title, "body": body, "labels": labels,
                               "html_url": f"https://github.com/o/r/issues/{number}"}
        return self.issues[number]

    def update_issue(self, number, body=None, title=None):
        self.issues[number]["body"] = body
        return self.issues[number]

    def upsert_comment(self, number, marker, body):
        self.comments[(number, marker)] = body
        return {"html_url": f"https://github.com/o/r/issues/{number}#comment"}


@pytest.fixture
def github(monkeypatch):
    recorder = RecordingGitHub()
    monkeypatch.setattr(scout_cli.GitHubClient, "from_env", classmethod(lambda cls, http: recorder))
    return recorder


def test_scout_opens_one_issue_per_week_and_validator_comments(tmp_path, fixtures_dir, github, as_of):
    args = ["--fixtures", str(fixtures_dir), "--out", str(tmp_path), "--now", as_of.isoformat()]
    assert scout_cli.main(args) == 0
    assert scout_cli.main(args) == 0  # a re-run in the same week updates instead of duplicating
    assert len(github.issues) == 1
    issue = github.issues[1]
    assert issue["labels"] == ["scout"] and issue["title"] == "Scout 2026-W43: 20 candidate niches"
    assert json.loads((tmp_path / "issue.json").read_text())["number"] == 1

    assert validator_cli.main(["--scout", str(tmp_path / "scout.json"), "--fixtures", str(fixtures_dir), "--out", str(tmp_path)]) == 0
    [(number, marker)] = github.comments
    assert number == 1 and marker == "<!-- factory:validator v1 -->"
    assert "Checks |" in github.issues[1]["body"]


def test_watcher_summary_is_included(tmp_path, fixtures_dir, github, as_of):
    summary = tmp_path / "watcher.md"
    summary.write_text("2 Actors, 0 broken.")
    scout_cli.main(["--fixtures", str(fixtures_dir), "--out", str(tmp_path), "--now", as_of.isoformat(),
                    "--watcher-summary", str(summary), "--dry-run"])
    assert "2 Actors, 0 broken." in (tmp_path / "issue_body.md").read_text()
    assert json.loads((tmp_path / "scout.json").read_text())["watcher_summary"] == "2 Actors, 0 broken."


class FailingAssessor:
    def __init__(self, *args, **kwargs):
        pass

    def assess(self, candidate):
        from factory.validator.assessment import AssessmentError

        raise AssessmentError("could not reach the Claude API")


def test_validator_exits_non_zero_when_every_assessment_fails(tmp_path, fixtures_dir, monkeypatch, as_of):
    scout_cli.main(["--fixtures", str(fixtures_dir), "--out", str(tmp_path), "--now", as_of.isoformat(), "--dry-run"])
    monkeypatch.setattr(validator_cli, "FixtureAssessor", FailingAssessor)
    code = validator_cli.main(["--scout", str(tmp_path / "scout.json"), "--fixtures", str(fixtures_dir),
                               "--out", str(tmp_path), "--dry-run"])
    assert code == 1
    assert "assessment failed" in (tmp_path / "brief.md").read_text()
