"""Minimal GitHub REST client for the issues and comments the agents write.

Inside GitHub Actions, GITHUB_TOKEN and GITHUB_REPOSITORY are set by the
runner. Writes are idempotent where a re-run could duplicate them: issues are
found by title and label, comments by a hidden marker.
"""

import os
from typing import Any

from factory.common.http import PoliteClient

API_BASE = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, http: PoliteClient, token: str, repo: str, api_base: str = API_BASE) -> None:
        if not token or not repo:
            raise GitHubError("GitHub token and repository are required")
        self._http = http
        self._repo = repo
        self._base = api_base.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @classmethod
    def from_env(cls, http: PoliteClient) -> "GitHubClient":
        token = os.environ.get("GITHUB_TOKEN", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if not token or not repo:
            raise GitHubError("Set GITHUB_TOKEN and GITHUB_REPOSITORY (both are automatic in GitHub Actions)")
        return cls(http, token, repo)

    def ensure_label(self, name: str, color: str = "ededed", description: str = "") -> None:
        self._call(
            "POST", f"/repos/{self._repo}/labels",
            json={"name": name, "color": color, "description": description},
            ok=(201, 422),  # 422: the label already exists
        )

    def find_open_issue(self, title: str, label: str) -> dict[str, Any] | None:
        issues = self._call(
            "GET", f"/repos/{self._repo}/issues",
            params={"state": "open", "labels": label, "per_page": 100},
        ).json()
        for issue in issues:
            if issue.get("title") == title and "pull_request" not in issue:
                return issue
        return None

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        return self._call(
            "POST", f"/repos/{self._repo}/issues",
            json={"title": title, "body": body, "labels": labels}, ok=(201,),
        ).json()

    def update_issue(self, number: int, *, body: str | None = None, title: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if body is not None:
            payload["body"] = body
        if title is not None:
            payload["title"] = title
        return self._call("PATCH", f"/repos/{self._repo}/issues/{number}", json=payload).json()

    def get_issue(self, number: int) -> dict[str, Any]:
        return self._call("GET", f"/repos/{self._repo}/issues/{number}").json()

    def find_issue(self, title: str, label: str, state: str = "all") -> dict[str, Any] | None:
        """The most recent issue with this exact title and label, open or closed by default."""
        issues = self._call(
            "GET", f"/repos/{self._repo}/issues",
            params={"state": state, "labels": label, "per_page": 100, "sort": "created", "direction": "desc"},
        ).json()
        return next((i for i in issues if i.get("title") == title and "pull_request" not in i), None)

    def list_comments(self, number: int) -> list[dict[str, Any]]:
        return self._call(
            "GET", f"/repos/{self._repo}/issues/{number}/comments", params={"per_page": 100},
        ).json()

    def add_comment(self, number: int, body: str) -> dict[str, Any]:
        return self._call(
            "POST", f"/repos/{self._repo}/issues/{number}/comments", json={"body": body}, ok=(201,),
        ).json()

    def upsert_comment(self, number: int, marker: str, body: str) -> dict[str, Any]:
        """Edit the comment containing `marker` if there is one, else add a comment."""
        comments = self._call(
            "GET", f"/repos/{self._repo}/issues/{number}/comments", params={"per_page": 100},
        ).json()
        for comment in comments:
            if marker in (comment.get("body") or ""):
                return self._call(
                    "PATCH", f"/repos/{self._repo}/issues/comments/{comment['id']}", json={"body": body},
                ).json()
        return self._call(
            "POST", f"/repos/{self._repo}/issues/{number}/comments", json={"body": body}, ok=(201,),
        ).json()

    def _call(self, method: str, path: str, ok: tuple[int, ...] = (200,), **kwargs: Any):
        response = self._http.request(method, self._base + path, headers=self._headers, **kwargs)
        if response.status_code not in ok:
            raise GitHubError(f"{method} {path} -> {response.status_code}: {response.text[:300]}")
        return response
