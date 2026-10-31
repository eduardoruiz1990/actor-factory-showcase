"""Saved tasks for an Actor: ready-made inputs users can run in one click, kept in `.actor/tasks.json`.

Apify's Actor quality score asks for a published task. After each deploy the
Publisher creates or updates every task in the file through the Apify API, then
publishes the ones marked `publish` in a second request. Publishing has extra
rules (the Actor must be public, `publicConfig` must name the input fields and a
dataset view), and a failed publish request changes nothing, so it is kept
separate: the task always exists, and a refusal is a warning with Apify's reason.
"""

import json
from pathlib import Path
from typing import Any

from factory.common.http import PoliteClient

TASK_FIELDS = ("title", "description", "input", "options")


def load_tasks(actor_dir: Path) -> list[dict[str, Any]]:
    path = actor_dir / ".actor" / "tasks.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [t for t in data.get("tasks", []) if isinstance(t, dict) and t.get("name")]


def sync_tasks(http: PoliteClient, api_base: str, owner: str, actor_id: str, actor_public: bool,
               tasks: list[dict[str, Any]], token: str) -> None:
    for task in tasks:
        sync_task(http, api_base, owner, actor_id, actor_public, task, token)


def sync_task(http: PoliteClient, api_base: str, owner: str, actor_id: str, actor_public: bool,
              task: dict[str, Any], token: str) -> bool:
    """Create or update one task, then publish it if asked; False (with a warning) when a step failed."""
    headers = {"Authorization": f"Bearer {token}"}
    name = task["name"]
    url = f"{api_base}/actor-tasks/{owner}~{name}"
    fields = {k: task[k] for k in TASK_FIELDS if k in task}
    existing = http.get(url, headers=headers)
    if existing.status_code == 200:
        response = http.request("PUT", url, json=fields, headers=headers)
    elif existing.status_code == 404:
        response = http.request("POST", f"{api_base}/actor-tasks", json={"actId": actor_id, "name": name, **fields},
                                headers=headers)
    else:
        return _warn(name, "could not be read", existing)
    if response.status_code not in (200, 201):
        return _warn(name, "was not saved", response)
    saved = response.json().get("data") or {}
    print(f"Task {name} saved: {saved.get('title') or name}")
    if not task.get("publish"):
        return True
    if not actor_public:
        print(f"::warning title=Publisher::Task {name} is published once the Actor itself is public.")
        return True
    publish = http.request("PUT", url, json={"publicConfig": task.get("publicConfig") or {}, "isPublic": True},
                           headers=headers)
    if publish.status_code != 200:
        return _warn(name, "was saved but not published", publish)
    print(f"Task {name} published")
    return True


def _warn(name: str, what: str, response: Any) -> bool:
    print(f"::warning title=Publisher::Task {name} {what} (HTTP {response.status_code}): {response.text[:300]}")
    return False
