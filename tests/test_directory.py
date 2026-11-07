import gzip
import json

import httpx
import pytest

from factory.common.http import PoliteClient
from factory.directory import DirectoryError, fetch, main, open_store, read_record, upload, write_record

API = "https://api.apify.com/v2"
STORE = {"id": "STORE1", "generalAccess": "RESTRICTED"}


def api(records=None, store=STORE, seen=None, status=200):
    records = {} if records is None else records

    def handler(request):
        if seen is not None:
            seen.append((request.method, request.url.path, request.headers.get("authorization"),
                         request.headers.get("content-encoding"), request.content))
        path = request.url.path
        if status != 200:
            return httpx.Response(status, text="no")
        if path == "/v2/key-value-stores" and request.method == "POST":
            assert request.url.params["name"] == "job-board-directory"
            return httpx.Response(201, json={"data": store})
        if path == f"/v2/key-value-stores/{store['id']}":
            return httpx.Response(200, json={"data": {**store, **json.loads(request.content)}})
        key = path.rsplit("/", 1)[1]
        if request.method == "PUT":
            records[key] = request.content
            return httpx.Response(201)
        return httpx.Response(200, content=records[key]) if key in records else httpx.Response(404)

    return PoliteClient(user_agent="t", min_interval=0, max_retries=0, transport=httpx.MockTransport(handler))


def test_the_store_opens_and_becomes_readable_by_id():
    seen = []
    assert open_store(api(seen=seen), API, "job-board-directory", "secret") == "STORE1"
    assert seen[1][0] == "PUT" and json.loads(seen[1][4]) == {"generalAccess": "ANYONE_WITH_ID_CAN_READ"}
    assert all(call[2] == "Bearer secret" for call in seen)


def test_a_store_already_open_is_left_alone():
    seen = []
    open_store(api(store={"id": "STORE1", "generalAccess": "ANYONE_WITH_ID_CAN_READ"}, seen=seen), API, "job-board-directory", "secret")
    assert [call[0] for call in seen] == ["POST"]


def test_a_refused_store_is_an_error():
    with pytest.raises(DirectoryError, match="403"):
        open_store(api(status=403), API, "job-board-directory", "secret")


def test_upload_marks_the_index_as_gzip_and_fetch_gets_both_back(tmp_path):
    (tmp_path / "boards.json").write_text('{"boards": {}}')
    packed = gzip.compress(b'{"boards": {"acme": {}}}')
    (tmp_path / "index.json.gz").write_bytes(packed)
    records, seen = {}, []
    upload(api(records, seen=seen), API, "STORE1", tmp_path, "secret", 1000)
    encodings = {call[1].rsplit("/", 1)[1]: call[3] for call in seen}
    assert encodings == {"boards.json": None, "index.json.gz": "gzip"} and records["index.json.gz"] == packed
    back = tmp_path / "back"
    fetch(api(records), API, "STORE1", back, "secret")
    assert (back / "boards.json").read_text() == '{"boards": {}}'
    assert json.loads((back / "index.json").read_text()) == {"boards": {"acme": {}}}


def test_a_first_run_has_nothing_to_fetch(tmp_path):
    fetch(api(), API, "STORE1", tmp_path / "new", "secret")
    assert list((tmp_path / "new").iterdir()) == []
    assert read_record(api(), API, "STORE1", "boards.json", "secret") is None


def test_an_oversized_index_fails_before_uploading():
    seen = []
    with pytest.raises(DirectoryError, match="over the 10"):
        write_record(api(seen=seen), API, "STORE1", "index.json.gz", b"x" * 11, "secret", True, 10)
    assert seen == []


def test_main_needs_a_token(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    assert main(["fetch", str(tmp_path)]) == 1
    assert "APIFY_TOKEN" in capsys.readouterr().out
