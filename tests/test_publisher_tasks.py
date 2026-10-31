import json
from pathlib import Path

import httpx

from factory.common.http import PoliteClient
from factory.publisher.listing import load_actor
from factory.publisher.tasks import load_tasks, sync_task

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.apify.com/v2"
TASK = {"name": "daily-jobs", "title": "Daily jobs", "input": {"boardTokens": ["airbnb"]}, "publish": True,
        "publicConfig": {"inputSchemaFields": ["boardTokens"], "datasetView": "overview"}}


def fake_api(exists=True, publish_status=200):
    seen = []

    def handler(request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, body))
        if request.method == "GET":
            return httpx.Response(200 if exists else 404, json={"data": {"name": "daily-jobs"}})
        if request.method == "PUT" and body and "isPublic" in body:
            return httpx.Response(publish_status, json={"error": {"message": "datasetView must be set"}})
        return httpx.Response(201 if request.method == "POST" else 200, json={"data": {"title": "Daily jobs"}})

    http = PoliteClient(user_agent="t", min_interval=0, max_retries=0, transport=httpx.MockTransport(handler))
    return http, seen


def test_a_new_task_is_created_then_published_in_a_separate_request():
    http, seen = fake_api(exists=False)
    assert sync_task(http, API, "guayox", "ACT1", True, TASK, "secret")
    assert [(m, p) for m, p, _ in seen] == [("GET", "/v2/actor-tasks/guayox~daily-jobs"), ("POST", "/v2/actor-tasks"),
                                           ("PUT", "/v2/actor-tasks/guayox~daily-jobs")]
    assert seen[1][2] == {"actId": "ACT1", "name": "daily-jobs", "title": "Daily jobs", "input": {"boardTokens": ["airbnb"]}}
    assert seen[2][2] == {"publicConfig": TASK["publicConfig"], "isPublic": True}


def test_an_existing_task_is_updated_and_a_refused_publish_is_only_a_warning(capsys):
    http, seen = fake_api(exists=True, publish_status=400)
    assert not sync_task(http, API, "guayox", "ACT1", True, TASK, "secret")
    assert [m for m, _, _ in seen] == ["GET", "PUT", "PUT"]  # saved first, so the task exists anyway
    assert "was saved but not published (HTTP 400): " in capsys.readouterr().out


def test_publishing_waits_until_the_actor_is_public(capsys):
    http, seen = fake_api(exists=False)
    assert sync_task(http, API, "guayox", "ACT1", False, TASK, "secret")
    assert [m for m, _, _ in seen] == ["GET", "POST"] and "once the Actor itself is public" in capsys.readouterr().out
    http, seen = fake_api(exists=False)
    assert sync_task(http, API, "guayox", "ACT1", True, {**TASK, "publish": False}, "secret")
    assert [m for m, _, _ in seen] == ["GET", "POST"]


def test_every_actors_tasks_fit_apifys_rules():
    for actor_dir in sorted((ROOT / "actors").glob("*/")):
        tasks = load_tasks(actor_dir)
        input_fields = json.loads((actor_dir / ".actor" / "input_schema.json").read_text())["properties"]
        views = json.loads((actor_dir / ".actor" / "dataset_schema.json").read_text()).get("views", {})
        assert len([t for t in tasks if t.get("publish")]) <= 10
        for task in tasks:
            name = task["name"]
            assert 3 <= len(name) <= 63 and name == name.lower() and set(name) <= set("abcdefghijklmnopqrstuvwxyz0123456789-")
            assert set(task["input"]) <= set(input_fields), name  # only fields the Actor accepts
            config = task.get("publicConfig") or {}
            if task.get("publish"):
                assert set(config["inputSchemaFields"]) <= set(input_fields) and config["datasetView"] in views, name
                assert len(config.get("seoTitle", "")) <= 60 and len(config.get("seoDescription", "")) <= 160, name
        assert load_actor(actor_dir)  # the folder is still a valid Actor
