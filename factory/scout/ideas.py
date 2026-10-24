"""Read Apify Ideas: the public export for the list, each idea's page for its upvotes.

The Ideas page (https://apify.com/ideas) loads its list in the browser, so the
HTML holds no ideas. The page's own "Export ideas" button calls
https://apify.com/api/ideas/download?format=json&status=toDevelop, which
returns every idea still open to develop (title, description, categories,
url) but no vote counts. Each idea's own page shows its upvotes in an element
marked data-test="upvotes". apify.com/robots.txt allows both.
"""

import re
from typing import Any

from factory.scout.models import Idea

# Ideas in the export are all "toDevelop"; config.yaml's open statuses include this value.
EXPORT_STATUS = "open_to_develop"

_UPVOTES_TEXT = re.compile(r'data-test="upvotes"[^>]*>\s*([\d,]+)\s*<')
_UPVOTES_LABEL = re.compile(r'aria-label="([\d,]+) upvotes?"')


def parse_ideas_export(data: Any) -> list[Idea]:
    """Ideas from the export JSON (a list of objects). Malformed entries are skipped."""
    if not isinstance(data, list):
        return []
    ideas: dict[str, Idea] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        title, url = entry.get("title"), entry.get("url")
        if not isinstance(title, str) or not title.strip() or not isinstance(url, str) or not url:
            continue
        description = entry.get("description") if isinstance(entry.get("description"), str) else ""
        ideas.setdefault(url, Idea(title=title.strip(), url=url, status=EXPORT_STATUS, description=description.strip()[:300]))
    return list(ideas.values())


def parse_upvotes(html: str) -> int | None:
    """The upvote count on an idea's page, or None when the page does not show one."""
    match = _UPVOTES_TEXT.search(html) or _UPVOTES_LABEL.search(html)
    return int(match.group(1).replace(",", "")) if match else None
