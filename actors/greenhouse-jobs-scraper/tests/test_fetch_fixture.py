import asyncio
import json
from pathlib import Path

import httpx2
import pytest

from tests.fetch_fixture import fetch

URL = 'https://api.example.com/v1/items'


def source(robots: str | None = None, status: int = 200, body: object = None):
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == '/robots.txt':
            return httpx2.Response(404) if robots is None else httpx2.Response(200, text=robots)
        if isinstance(body, str):
            return httpx2.Response(status, text=body)
        return httpx2.Response(status, json=body if body is not None else {'items': []})

    return httpx2.MockTransport(handler)


@pytest.fixture(autouse=True)
def in_actor_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def run(transport, out='tests/fixtures/items.json'):
    return asyncio.run(fetch(URL, Path(out), transport=transport))


def test_saves_json_through_the_privacy_guard():
    body = {'items': [{'title': 'Engineer', 'recruiter': 'Jane Doe', 'text': 'Write to jobs@example.com'}]}
    assert run(source(body=body)) == 0
    saved = json.loads(Path('tests/fixtures/items.json').read_text())
    assert saved == {'items': [{'title': 'Engineer', 'text': 'Write to [removed]'}]}


def test_saves_html_as_text():
    assert run(source(body='<html><p>Call +44 20 7946 0958</p></html>'), out='tests/fixtures/page.html') == 0
    assert Path('tests/fixtures/page.html').read_text() == '<html><p>Call [removed]</p></html>\n'


def test_robots_disallow_saves_nothing():
    assert run(source(robots='User-agent: *\nDisallow: /v1/\n')) == 1
    assert not Path('tests/fixtures').exists()


def test_error_status_saves_nothing():
    assert run(source(status=404)) == 1
    assert not Path('tests/fixtures').exists()


def test_refuses_paths_outside_the_fixtures_folder():
    assert run(source(), out='my_actor/items.json') == 1
    assert not Path('my_actor').exists()
