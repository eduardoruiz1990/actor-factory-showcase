import json
import shutil
from pathlib import Path

import httpx

from factory.common.config import load_config
from factory.common.http import PoliteClient
from factory.publisher.__main__ import sync_listing
from factory.publisher.listing import (
    SEO_DESCRIPTION_MAX, SEO_TITLE_MAX, changed_actors, load_actor, render_listing, store_fields,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "python-actor"


def test_changed_actors_only_counts_actor_folders_that_still_exist(tmp_path):
    shutil.copytree(TEMPLATE, tmp_path / "actors" / "jobs")
    (tmp_path / "actors" / "removed").mkdir(parents=True)
    files = ["actors/jobs/my_actor/source.py", "actors/removed/README.md", "factory/scout/run.py", "actors/README.md"]
    assert changed_actors(files, tmp_path) == ["jobs"]


def test_listing_has_the_text_and_pricing_to_enter():
    body = render_listing("my-actor", "guayox", load_actor(TEMPLATE), build_url="https://console.apify.com/b/1")
    assert body.startswith("<!-- factory:publisher my-actor -->")
    assert "https://console.apify.com/actors/guayox~my-actor" in body
    assert "| `apify-default-dataset-item` | Result | $0.002 per event ($2.00 per 1,000) | yes |" in body
    assert "| `apify-actor-start` | Actor start | keep Apify's default |  |" in body
    assert "Do not add another per-result event" in body
    assert "[build](https://console.apify.com/b/1)" in body


def test_seo_text_is_trimmed_to_store_limits():
    data = load_actor(TEMPLATE)
    data["listing"]["seoDescription"] = "x" * 400
    body = render_listing("my-actor", "guayox", data)
    assert f"({SEO_DESCRIPTION_MAX}/{SEO_DESCRIPTION_MAX})" in body


def test_store_fields_come_from_actor_json_and_listing_json():
    data = load_actor(TEMPLATE)
    data["actor"].update(title="Jobs Scraper", description="Every job.")
    data["listing"].update(categories=["JOBS", "NOT_A_CATEGORY"], seoTitle="t" * 80, seoDescription=" Jobs, as JSON. ")
    fields, unknown = store_fields(data, ["JOBS", "AUTOMATION"])
    assert fields == {"title": "Jobs Scraper", "description": "Every job.", "seoTitle": "t" * SEO_TITLE_MAX,
                      "seoDescription": "Jobs, as JSON.", "categories": ["JOBS"]}
    assert unknown == ["NOT_A_CATEGORY"]
    data["listing"] = {}
    assert "categories" not in store_fields(data, ["JOBS"])[0]


def test_sync_listing_sends_only_the_listing_fields(capsys):
    seen = []

    def api(request):
        seen.append((request.method, str(request.url), request.headers["authorization"], json.loads(request.content)))
        return httpx.Response(200 if len(seen) == 1 else 403, json={"data": {}})

    http = PoliteClient(user_agent="t", min_interval=0, max_retries=0, transport=httpx.MockTransport(api))
    url = "https://api.apify.com/v2/acts/guayox~jobs"
    assert sync_listing(http, url, "secret", {"categories": ["JOBS"]})
    assert seen == [("PUT", url, "Bearer secret", {"categories": ["JOBS"]})]
    assert not sync_listing(http, url, "secret", {"categories": ["JOBS"]})  # 403: a warning, not a failure
    assert "Store listing not updated (HTTP 403)" in capsys.readouterr().out
    assert not sync_listing(http, url, "secret", {}) and len(seen) == 2


def test_every_actor_lists_only_known_store_categories():
    known = load_config()["scout"]["store"]["categories"]
    for actor_dir in [TEMPLATE, *sorted((ROOT / "actors").glob("*/"))]:
        if (actor_dir / ".actor" / "actor.json").exists():
            assert store_fields(load_actor(actor_dir), known)[1] == [], actor_dir.name
