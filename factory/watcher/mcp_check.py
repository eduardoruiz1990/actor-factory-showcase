"""Live check of an MCP Actor, run on demand by .github/workflows/mcp-check.yml.

Connects to the deployed Actor's Standby URL as an MCP client, the way an AI agent
does, and calls its tools. The APIFY_TOKEN secret exists only in GitHub Actions, so
this cannot run from the development sandbox. Outside text in the answers is only
printed and compared, never followed.

    python -m factory.watcher.mcp_check            # exit 1 if any check fails
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.common.config import load_config
from factory.common.http import PoliteClient

PROTOCOL_VERSION = "2025-06-18"


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


class McpError(Exception):
    pass


def rpc(http: PoliteClient, url: str, token: str, request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    """One JSON-RPC call over Streamable HTTP; the server answers with JSON or with one server-sent event."""
    response = http.request(
        "POST", url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream",
                 "MCP-Protocol-Version": PROTOCOL_VERSION},
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
    )
    if response.status_code != 200:
        raise McpError(f"HTTP {response.status_code}: {response.text[:300]}")
    text = response.text
    if "text/event-stream" in response.headers.get("content-type", ""):
        data = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        text = data[-1] if data else ""
    try:
        body = json.loads(text)
    except ValueError as exc:
        raise McpError(f"not JSON: {text[:300]}") from exc
    if body.get("error"):
        raise McpError(f"JSON-RPC error: {json.dumps(body['error'])[:300]}")
    return body.get("result") or {}


def call_tool(http: PoliteClient, url: str, token: str, request_id: int, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = rpc(http, url, token, request_id, "tools/call", {"name": name, "arguments": arguments})
    if result.get("isError"):
        raise McpError(f"tool error: {json.dumps(result.get('content'))[:300]}")
    return result.get("structuredContent") or {}


def run_checks(http: PoliteClient, url: str, token: str, tools: list[str], board_checks: dict[str, str],
               paid_board: str, directory_search: dict[str, Any]) -> list[Check]:
    """Every check in order; connecting comes first, because nothing else can pass without it."""
    checks: list[Check] = []
    try:
        info = rpc(http, url, token, 1, "initialize", {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "actor-factory-check", "version": "1"}})
        server = info.get("serverInfo") or {}
        checks.append(Check("connect", bool(server), f"{server.get('name')} {server.get('version')}"))
    except Exception as exc:  # noqa: BLE001 (a failed check is the result, whatever the cause)
        return [Check("connect", False, str(exc))]

    def attempt(name: str, run: Any) -> None:
        try:
            checks.append(run())
        except Exception as exc:  # noqa: BLE001
            checks.append(Check(name, False, str(exc)))

    def listed() -> Check:
        names = [t.get("name") for t in rpc(http, url, token, 2, "tools/list", {}).get("tools", [])]
        return Check("tools/list", all(t in names for t in tools), ", ".join(str(n) for n in names))

    attempt("tools/list", listed)
    for offset, (company, board) in enumerate(board_checks.items()):
        def lookup(company: str = company, board: str = board, request_id: int = 10 + offset) -> Check:
            found = call_tool(http, url, token, request_id, "find_job_board", {"company": company})
            passed = found.get("board") == board and int(found.get("open_jobs") or 0) > 0
            return Check(f"find_job_board {company}", passed, json.dumps(found))

        attempt(f"find_job_board {company}", lookup)

    def paid() -> Check:
        # The one charged call: a single job, so the Standby run's dataset and charging are tested for about $0.002.
        found = call_tool(http, url, token, 90, "search_jobs", {"companies": [paid_board], "max_results": 1})
        titles = [job.get("title") for job in found.get("jobs", [])]
        return Check("search_jobs one job", found.get("charged_results") == 1 and len(titles) == 1,
                     f"boards={found.get('boards')} titles={titles} charged={found.get('charged_results')}")

    attempt("search_jobs one job", paid)

    def directory() -> Check:
        # Charged too, for one job: the directory must load on Apify and lead to a live board.
        found = call_tool(http, url, token, 91, "search_all_companies", {**directory_search, "max_results": 1})
        titles = [job.get("title") for job in found.get("jobs", [])]
        passed = found.get("charged_results") == 1 and len(titles) == 1 and int(found.get("boards_matched") or 0) > 0
        return Check("search_all_companies one job", passed,
                     f"matched={found.get('boards_matched')} titles={titles} note={found.get('note')}")

    attempt("search_all_companies one job", directory)
    return checks


def latest_run(http: PoliteClient, api_base: str, owner: str, actor: str, token: str) -> str:
    """The Actor's newest run as Apify records it. For information: the checks above decide pass or fail."""
    response = http.get(f"{api_base}/acts/{owner}~{actor}/runs", params={"desc": "true", "limit": 1},
                        headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200:
        return f"could not read runs (HTTP {response.status_code})"
    items = (response.json().get("data") or {}).get("items") or []
    if not items:
        return "no runs listed"
    run = items[0]
    return (f"status={run.get('status')} origin={(run.get('meta') or {}).get('origin')} "
            f"build={run.get('buildNumber')} started={run.get('startedAt')}")


def render(actor: str, url: str, checks: list[Check], run: str) -> str:
    lines = [f"## MCP live check: `{actor}`", "", f"Endpoint: `{url}`", "", "| Check | Result | Detail |", "|---|---|---|"]
    for check in checks:
        detail = check.detail.replace("|", "/").replace("\n", " ")[:300]
        lines.append(f"| {check.name} | {'✅' if check.passed else '❌'} | `{detail}` |")
    return "\n".join([*lines, "", f"Latest run: {run}", ""])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m factory.watcher.mcp_check")
    parser.add_argument("--url", help="Check this MCP endpoint instead of the deployed Actor's")
    parser.add_argument("--config")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    cfg = config["watcher"]["mcp_check"]
    owner, actor = config["owner"]["apify_username"], cfg["actor"]
    token = os.environ.get("APIFY_TOKEN", "")
    if not token and not args.url:
        print("::error title=MCP check::APIFY_TOKEN is not set")
        return 1
    url = args.url or f"https://{owner}--{actor}.apify.actor/mcp"
    with PoliteClient.from_config(config, timeout=float(cfg["timeout_seconds"])) as http:
        checks = run_checks(http, url, token, list(cfg["tools"]), dict(cfg["board_checks"]), cfg["paid_board"],
                            dict(cfg["directory_search"]))
        run = "not read (--url)" if args.url else latest_run(http, config["apify"]["api_base"], owner, actor, token)
    body = render(actor, url, checks, run)
    print(body)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(body + "\n")
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
