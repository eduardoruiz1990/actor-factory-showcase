import json

from factory.scout.ideas import normalise_status, parse_ideas_html

PAGE = "https://apify.com/ideas"


def test_parses_the_sample_ideas_page(fixtures_dir):
    ideas = parse_ideas_html((fixtures_dir / "apify" / "ideas.html").read_text(), PAGE)
    assert len(ideas) == 8
    top = ideas[0]  # sorted by upvotes
    assert top.title == "Federal grant opportunities from Grants.gov"
    assert top.upvotes == 96
    assert top.status == "new"
    assert top.url == "https://apify.com/ideas/federal-grant-opportunities-grants-gov"
    assert {i.status for i in ideas} == {"open_to_develop", "new", "in_progress", "completed"}


def test_finds_ideas_nested_anywhere_in_embedded_json():
    data = {"a": {"b": [{"x": 1}, {"node": {"name": "Idea one", "voteCount": 4, "href": "/ideas/one", "state": "Open"}}]}}
    html = f'<html><script type="application/json">{json.dumps(data)}</script></html>'
    [idea] = parse_ideas_html(html, PAGE)
    assert (idea.title, idea.upvotes, idea.url, idea.status) == ("Idea one", 4, "https://apify.com/ideas/one", "open")


def test_ignores_objects_without_votes_and_duplicates():
    data = [{"title": "Not an idea"}, {"title": "Dup", "upvotes": 2, "slug": "dup"}, {"title": "Dup", "upvotes": 2, "slug": "dup"}]
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    ideas = parse_ideas_html(html, PAGE)
    assert [i.title for i in ideas] == ["Dup"]


def test_page_without_embedded_json_yields_nothing():
    assert parse_ideas_html("<html><body><h1>Ideas</h1></body></html>", PAGE) == []


def test_normalise_status():
    assert normalise_status("Open to develop") == "open_to_develop"
    assert normalise_status(" In progress ") == "in_progress"
