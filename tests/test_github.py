import json

import httpx
import pytest

from factory.common.github import GitHubClient, GitHubError
from factory.common.http import PoliteClient


class FakeGitHub:
    """Just enough of the REST API to exercise GitHubClient."""

    def __init__(self):
        self.issues = []
        self.comments = []
        self.labels = set()
        self.calls = []

    def __call__(self, request):
        path, method = request.url.path, request.method
        body = json.loads(request.content) if request.content else None
        self.calls.append((method, path))
        assert request.headers["Authorization"] == "Bearer t0ken"
        if path.endswith("/labels") and method == "POST":
            if body["name"] in self.labels:
                return httpx.Response(422, json={"message": "already_exists"})
            self.labels.add(body["name"])
            return httpx.Response(201, json={})
        if path.endswith("/issues") and method == "GET":
            return httpx.Response(200, json=self.issues)
        if path.endswith("/issues") and method == "POST":
            issue = {"number": len(self.issues) + 1, "html_url": f"https://github.com/o/r/issues/{len(self.issues) + 1}", **body}
            self.issues.append(issue)
            return httpx.Response(201, json=issue)
        if "/issues/comments/" in path and method == "PATCH":
            comment = next(c for c in self.comments if c["id"] == int(path.rsplit("/", 1)[1]))
            comment.update(body)
            return httpx.Response(200, json=comment)
        if path.endswith("/comments") and method == "GET":
            return httpx.Response(200, json=self.comments)
        if path.endswith("/comments") and method == "POST":
            comment = {"id": 100 + len(self.comments), "html_url": "https://github.com/c", **body}
            self.comments.append(comment)
            return httpx.Response(201, json=comment)
        if "/issues/" in path and method == "PATCH":
            issue = self.issues[int(path.rsplit("/", 1)[1]) - 1]
            issue.update(body)
            return httpx.Response(200, json=issue)
        return httpx.Response(500, json={"message": f"unexpected {method} {path}"})


@pytest.fixture
def github():
    fake = FakeGitHub()
    http = PoliteClient(user_agent="t", min_interval=0, max_retries=0, transport=httpx.MockTransport(fake), sleep=lambda s: None)
    return GitHubClient(http, "t0ken", "o/r"), fake


def test_ensure_label_tolerates_existing_label(github):
    client, fake = github
    client.ensure_label("scout")
    client.ensure_label("scout")
    assert fake.labels == {"scout"}


def test_find_open_issue_matches_exact_title(github):
    client, fake = github
    client.create_issue("Scout 2026-W43: 20 candidate niches", "body", ["scout"])
    assert client.find_open_issue("Scout 2026-W43: 20 candidate niches", "scout")["number"] == 1
    assert client.find_open_issue("Scout 2026-W44: 20 candidate niches", "scout") is None


def test_upsert_comment_edits_the_marked_comment(github):
    client, fake = github
    client.create_issue("t", "b", [])
    client.upsert_comment(1, "<!-- marker -->", "<!-- marker -->\nfirst")
    client.upsert_comment(1, "<!-- marker -->", "<!-- marker -->\nsecond")
    assert len(fake.comments) == 1
    assert fake.comments[0]["body"].endswith("second")


def test_errors_raise_with_status(github):
    client, fake = github
    with pytest.raises(GitHubError, match="500"):
        client.get_issue(99)


def test_from_env_requires_token_and_repo(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    with pytest.raises(GitHubError):
        GitHubClient.from_env(PoliteClient(user_agent="t"))
