"""Move the job directory to and from its Apify store (QUESTIONS Q29).

The Actor's own code builds the directory (actors/greenhouse-jobs-scraper/tools/build_directory.py);
this side holds APIFY_TOKEN and talks to the Apify API. Run by .github/workflows/directory.yml:

    python -m factory.directory fetch out/directory    # boards.json and the last index, if any
    python -m factory.directory upload out/directory   # boards.json and index.json.gz

The store is named, so it never expires, and readable by anyone with its ID, because a user's
Actor run must read it without the owner's token. It holds only job titles, locations and board names.
"""

import argparse
import gzip
import os
import sys
from pathlib import Path

from factory.common.config import load_config
from factory.common.http import PoliteClient

PUBLIC_READ = "ANYONE_WITH_ID_CAN_READ"
BOARDS = "boards.json"
INDEX = "index.json.gz"
LAST_INDEX = "index.json"


class DirectoryError(Exception):
    pass


def open_store(http: PoliteClient, api_base: str, name: str, token: str) -> str:
    """The store's ID, creating it if needed, and readable by ID without a token."""
    headers = {"Authorization": f"Bearer {token}"}
    response = http.request("POST", f"{api_base}/key-value-stores", params={"name": name}, headers=headers)
    if response.status_code not in (200, 201):
        raise DirectoryError(f"could not open the store (HTTP {response.status_code}): {response.text[:200]}")
    store = response.json()["data"]
    if store.get("generalAccess") != PUBLIC_READ:
        updated = http.request("PUT", f"{api_base}/key-value-stores/{store['id']}",
                               json={"generalAccess": PUBLIC_READ}, headers=headers)
        if updated.status_code != 200:
            raise DirectoryError(f"could not make the store readable (HTTP {updated.status_code}): {updated.text[:200]}")
    return store["id"]


def read_record(http: PoliteClient, api_base: str, store_id: str, key: str, token: str) -> bytes | None:
    response = http.get(f"{api_base}/key-value-stores/{store_id}/records/{key}",
                        headers={"Authorization": f"Bearer {token}"})
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise DirectoryError(f"could not read {key} (HTTP {response.status_code})")
    return response.content


def write_record(http: PoliteClient, api_base: str, store_id: str, key: str, body: bytes, token: str,
                 compressed: bool, limit: int) -> None:
    if len(body) > limit:
        raise DirectoryError(f"{key} is {len(body)} bytes, over the {limit} limit in config.yaml")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if compressed:
        headers["Content-Encoding"] = "gzip"
    response = http.request("PUT", f"{api_base}/key-value-stores/{store_id}/records/{key}", content=body,
                            headers=headers)
    if response.status_code not in (200, 201):
        raise DirectoryError(f"could not write {key} (HTTP {response.status_code}): {response.text[:200]}")


def fetch(http: PoliteClient, api_base: str, store_id: str, folder: Path, token: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    boards = read_record(http, api_base, store_id, BOARDS, token)
    if boards is not None:
        (folder / BOARDS).write_bytes(boards)
    index = read_record(http, api_base, store_id, INDEX, token)
    if index is not None:
        # The client normally unpacks a gzip response already; a record stored as raw gzip bytes is unpacked here.
        (folder / LAST_INDEX).write_bytes(gzip.decompress(index) if index[:2] == b"\x1f\x8b" else index)


def upload(http: PoliteClient, api_base: str, store_id: str, folder: Path, token: str, limit: int) -> None:
    write_record(http, api_base, store_id, BOARDS, (folder / BOARDS).read_bytes(), token, False, limit)
    write_record(http, api_base, store_id, INDEX, (folder / INDEX).read_bytes(), token, True, limit)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m factory.directory")
    parser.add_argument("command", choices=["fetch", "upload"])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--config")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        print("::error title=Directory::APIFY_TOKEN is not set")
        return 1
    api_base, cfg = config["apify"]["api_base"], config["directory"]
    with PoliteClient.from_config(config) as http:
        store_id = open_store(http, api_base, cfg["store_name"], token)
        if args.command == "fetch":
            fetch(http, api_base, store_id, args.folder, token)
        else:
            upload(http, api_base, store_id, args.folder, token, int(cfg["max_record_bytes"]))
    line = f"Directory store ID: `{store_id}` ({args.command})"
    print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
