"""Parse the Apify Ideas page (https://apify.com/ideas).

The page's markup could not be inspected from the development sandbox
(apify.com is blocked there), so the parser does not rely on CSS classes. It
reads the JSON the page embeds for its framework (a Next.js __NEXT_DATA__
script or any other application/json script) and collects every object that
looks like an idea: a title plus an upvote count. If the page changes shape
and nothing is found, Scout says so in the weekly issue instead of failing
silently. See docs/QUESTIONS.md Q4.
"""

import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from factory.scout.models import Idea

TITLE_KEYS = ("title", "name")
VOTE_KEYS = ("upvotes", "upvoteCount", "upvotesCount", "votes", "voteCount", "votesCount", "likes")
STATUS_KEYS = ("status", "state", "stage")
URL_KEYS = ("url", "href", "permalink")
SLUG_KEYS = ("slug", "id")
TEXT_KEYS = ("description", "summary", "text")


def parse_ideas_html(html: str, page_url: str) -> list[Idea]:
    ideas: dict[str, Idea] = {}
    for blob in _json_scripts(html):
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        for obj in _walk(data):
            idea = _as_idea(obj, page_url)
            if idea is not None:
                ideas.setdefault(idea.url, idea)
    return sorted(ideas.values(), key=lambda i: (-i.upvotes, i.title))


def normalise_status(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _as_idea(obj: dict[str, Any], page_url: str) -> Idea | None:
    title = next((obj[k] for k in TITLE_KEYS if isinstance(obj.get(k), str) and obj[k].strip()), None)
    votes = next((obj[k] for k in VOTE_KEYS if isinstance(obj.get(k), int) and not isinstance(obj[k], bool)), None)
    if title is None or votes is None:
        return None
    url = next((obj[k] for k in URL_KEYS if isinstance(obj.get(k), str) and obj[k]), None)
    if url is None:
        slug = next((obj[k] for k in SLUG_KEYS if isinstance(obj.get(k), str) and obj[k]), None)
        url = f"{page_url.rstrip('/')}/{slug}" if slug else f"{page_url}#{normalise_status(title)}"
    status = next((obj[k] for k in STATUS_KEYS if isinstance(obj.get(k), str)), "")
    text = next((obj[k] for k in TEXT_KEYS if isinstance(obj.get(k), str)), "")
    return Idea(
        title=title.strip(),
        url=urljoin(page_url, url),
        upvotes=votes,
        status=normalise_status(status),
        description=text.strip()[:300],
    )


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _json_scripts(html: str) -> list[str]:
    collector = _ScriptCollector()
    collector.feed(html)
    return collector.blobs


class _ScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blobs: list[str] = []
        self._capturing = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        attributes = dict(attrs)
        script_type = (attributes.get("type") or "").lower()
        if attributes.get("id") == "__NEXT_DATA__" or script_type in ("application/json", "application/ld+json"):
            self._capturing = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capturing:
            self.blobs.append("".join(self._buffer))
            self._capturing = False
