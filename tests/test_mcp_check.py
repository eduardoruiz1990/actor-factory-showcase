import json

import httpx
import pytest

from factory.common.http import PoliteClient
from factory.watcher.mcp_check import latest_run, main, render, run_checks

URL = "https://guayox--ats-jobs-mcp-server.apify.actor/mcp"
BOARDS = {"notion": "ashby:notion", "ramp": "ashby:ramp"}
TOOLS = ["find_job_board", "search_jobs", "search_all_companies"]
FOUND = {"notion": {"company": "notion", "board": "ashby:notion", "platform": "ashby", "open_jobs": 154},
         "ramp": {"company": "ramp", "board": "ashby:ramp", "platform": "ashby", "open_jobs": 171,
                  "other_boards": {"ramp": 1}}}
SEARCH = {"boards": {"ashby:notion": "ashby:notion"}, "jobs": [{"title": "Engineer"}], "charged_results": 1}
DIRECTORY = {"boards_matched": 120, "boards_read": 1, "jobs": [{"title": "Engineer"}], "charged_results": 1}


def server(found=FOUND, search=SEARCH, directory=DIRECTORY, status=200, sse=False, seen=None):
    def handler(request):
        body = json.loads(request.content)
        if seen is not None:
            seen.append((request.headers.get("authorization"), body["method"]))
        if status != 200:
            return httpx.Response(status, text="Unauthorized")
        result = {}
        if body["method"] == "initialize":
            result = {"serverInfo": {"name": "ats-jobs", "version": "0.4"}}
        elif body["method"] == "tools/list":
            result = {"tools": [{"name": n} for n in TOOLS]}
        elif body["params"]["name"] == "find_job_board":
            result = {"structuredContent": found[body["params"]["arguments"]["company"]]}
        elif body["params"]["name"] == "search_all_companies":
            result = {"structuredContent": directory}
        else:
            result = {"structuredContent": search}
        payload = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result})
        if sse:
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=f"event: message\ndata: {payload}\n\n")
        return httpx.Response(200, headers={"content-type": "application/json"}, text=payload)

    return PoliteClient(user_agent="t", min_interval=0, max_retries=0, transport=httpx.MockTransport(handler))


def run(http):
    return run_checks(http, URL, "secret", TOOLS, BOARDS, "ashby:notion", {"title_keywords": ["engineer"]})


@pytest.mark.parametrize("sse", [False, True])
def test_a_healthy_server_passes_every_check(sse):
    seen = []
    checks = run(server(sse=sse, seen=seen))
    assert [c.name for c in checks] == ["connect", "tools/list", "find_job_board notion", "find_job_board ramp",
                                        "search_jobs one job", "search_all_companies one job"]
    assert all(c.passed for c in checks)
    assert all(auth == "Bearer secret" for auth, _ in seen)


def test_an_unreachable_server_fails_at_connect_and_calls_nothing_else():
    seen = []
    checks = run(server(status=401, seen=seen))
    assert [(c.name, c.passed) for c in checks] == [("connect", False)]
    assert "401" in checks[0].detail and [m for _, m in seen] == ["initialize"]


def test_a_name_resolved_to_the_wrong_board_fails():
    found = FOUND | {"ramp": {"company": "ramp", "board": "ramp", "platform": "greenhouse", "open_jobs": 1}}
    failed = [c.name for c in run(server(found=found)) if not c.passed]
    assert failed == ["find_job_board ramp"]


def test_a_search_that_charges_nothing_fails():
    failed = [c.name for c in run(server(search={"boards": {}, "jobs": [], "charged_results": 0})) if not c.passed]
    assert failed == ["search_jobs one job"]


def test_a_directory_that_cannot_be_read_fails():
    unavailable = {"jobs": [], "charged_results": 0, "note": "The company directory could not be read."}
    checks = run(server(directory=unavailable))
    assert [c.name for c in checks if not c.passed] == ["search_all_companies one job"]
    assert "could not be read" in checks[-1].detail


def test_latest_run_describes_the_newest_run_and_survives_an_error():
    def handler(request):
        assert request.url.params["desc"] == "true"
        return httpx.Response(200, json={"data": {"items": [{"status": "RUNNING", "meta": {"origin": "STANDBY"},
                                                             "buildNumber": "0.4.1", "startedAt": "2026-11-07T18:00:00Z"}]}})

    http = PoliteClient(user_agent="t", min_interval=0, max_retries=0, transport=httpx.MockTransport(handler))
    text = latest_run(http, "https://api.apify.com/v2", "guayox", "ats-jobs-mcp-server", "secret")
    assert "origin=STANDBY" in text and "build=0.4.1" in text
    denied = PoliteClient(user_agent="t", min_interval=0, max_retries=0,
                          transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    assert "403" in latest_run(denied, "https://api.apify.com/v2", "guayox", "ats-jobs-mcp-server", "secret")


def test_the_token_never_reaches_the_report():
    checks = run(server())
    assert "secret" not in render("ats-jobs-mcp-server", URL, checks, "status=RUNNING")


def test_main_needs_a_token(monkeypatch, capsys):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    assert main([]) == 1
    assert "APIFY_TOKEN" in capsys.readouterr().out
