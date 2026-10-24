import json

import httpx
import pytest

from factory.common.http import PoliteClient
from factory.scout.ideas import EXPORT_STATUS, parse_ideas_export, parse_upvotes
from factory.scout.run import fetch_ideas
from factory.scout.sources import FixtureSource, LiveSource


def test_parses_the_real_export_sample(fixtures_dir):
    data = json.loads((fixtures_dir / "apify" / "ideas_export_real_sample.json").read_text())
    ideas = parse_ideas_export(data)
    assert [i.title for i in ideas] == ["Bniconnectglobal scraper", "BuzzSumo Scraper", "Flipkey Scraper"]
    assert ideas[1].url == "https://apify.com/ideas/buzzsumo-scraper"
    assert all(i.status == EXPORT_STATUS and i.upvotes == 0 for i in ideas)
    assert all(len(i.description) <= 300 for i in ideas)


def test_reads_upvotes_from_real_idea_page_markup(fixtures_dir):
    assert parse_upvotes((fixtures_dir / "apify" / "idea_page_real_snippet.html").read_text()) == 0
    assert parse_upvotes('<span data-test="upvotes" class="x">1,204</span>') == 1204
    assert parse_upvotes('<span aria-label="7 upvotes" class="x"></span>') == 7
    assert parse_upvotes("<html><body>No votes shown</body></html>") is None


def test_malformed_export_entries_are_skipped():
    data = [{"title": "Ok", "url": "https://apify.com/ideas/ok"}, {"title": ""}, "junk", {"url": "u"},
            {"title": "Ok again", "url": "https://apify.com/ideas/ok"}]
    assert [i.title for i in parse_ideas_export(data)] == ["Ok"]
    assert parse_ideas_export({"not": "a list"}) == []


def test_fetch_ideas_attaches_upvotes_and_reports_unknowns(fixtures_dir):
    warnings = []
    ideas = fetch_ideas(FixtureSource(fixtures_dir), max_pages=100, warnings=warnings)
    assert [(i.title, i.upvotes) for i in ideas[:2]] == [
        ("Federal grant opportunities from Grants.gov", 96), ("PyPI package metadata scraper", 31)]
    wiki = next(i for i in ideas if i.title.startswith("Wikipedia"))
    assert wiki.upvotes == 0  # its page is missing in the fixtures
    assert warnings == ["Upvotes unknown for 1 of 6 ideas; they count as 0."]


def test_max_pages_limits_requests(fixtures_dir):
    source = FixtureSource(fixtures_dir)
    warnings = []
    fetch_ideas(source, max_pages=2, warnings=warnings)
    assert sum(1 for kind, _ in source.requests if kind == "idea_page") == 2
    assert warnings == ["Upvotes unknown for 4 of 6 ideas; they count as 0."]


class EmptySource(FixtureSource):
    def ideas_export(self):
        return None


def test_missing_export_is_a_warning(fixtures_dir):
    warnings = []
    assert fetch_ideas(EmptySource(fixtures_dir), 10, warnings) == []
    assert warnings == ["Ideas export could not be fetched."]


@pytest.fixture
def live_source():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.path == "/api/ideas/download":
            return httpx.Response(200, json=[{"title": "T", "url": "https://apify.com/ideas/t"}])
        return httpx.Response(200, text='<span data-test="upvotes">4</span>')

    http = PoliteClient(user_agent="t", min_interval=0, max_retries=0, transport=httpx.MockTransport(handler),
                        sleep=lambda s: None)
    source = LiveSource(http, api_base="https://api.apify.com/v2", ideas_url="https://apify.com/ideas",
                        ideas_export_url="https://apify.com/api/ideas/download?format=json&status=toDevelop")
    return source, seen


def test_live_source_reads_export_and_pages(live_source):
    source, seen = live_source
    warnings = []
    [idea] = fetch_ideas(source, 10, warnings)
    assert (idea.title, idea.upvotes) == ("T", 4)
    assert seen == ["https://apify.com/api/ideas/download?format=json&status=toDevelop", "https://apify.com/ideas/t"]


@pytest.mark.parametrize("url", ["https://evil.example/ideas/t", "http://169.254.169.254/latest", "https://apify.com/store"])
def test_live_source_only_fetches_idea_pages_on_apify(live_source, url):
    source, seen = live_source
    assert source.idea_page(url) is None
    assert seen == []
