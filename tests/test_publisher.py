import shutil
from pathlib import Path

from factory.publisher.listing import SEO_DESCRIPTION_MAX, changed_actors, load_actor, render_listing

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
