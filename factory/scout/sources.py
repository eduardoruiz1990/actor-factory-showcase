"""Where Scout's data comes from: the live Apify API, or saved fixtures.

LiveSource needs network access to api.apify.com and apify.com, which the
development sandbox blocks; it runs in GitHub Actions. FixtureSource serves the
saved sample responses in tests/fixtures/apify/ so the pipeline can be tested
and dry-run anywhere.
"""

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from factory.common.http import PoliteClient

log = logging.getLogger(__name__)


class ScoutSource(Protocol):
    def store_page(self, *, category: str | None, offset: int, limit: int, sort_by: str) -> dict[str, Any]:
        """One page of GET /v2/store: the `data` object (total, offset, limit, count, items)."""

    def actor_detail(self, actor_id: str) -> dict[str, Any] | None:
        """The `data` object of GET /v2/acts/{actorId}, or None when unavailable."""

    def ideas_html(self) -> str | None:
        """The Ideas page HTML, or None when it could not be fetched."""


class LiveSource:
    def __init__(
        self,
        http: PoliteClient,
        api_base: str,
        ideas_url: str,
        apify_token: str | None = None,
        raw_dir: Path | None = None,
    ) -> None:
        self._http = http
        self._api_base = api_base.rstrip("/")
        self._ideas_url = ideas_url
        self._token = apify_token
        self._raw_dir = raw_dir

    def store_page(self, *, category: str | None, offset: int, limit: int, sort_by: str) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset, "sortBy": sort_by}
        if category:
            params["category"] = category
        # The Store endpoint is public; no token is sent.
        payload = self._http.get_json(f"{self._api_base}/store", params=params)
        self._save(f"store/{category or 'all'}_{offset}.json", payload)
        return payload["data"]

    def actor_detail(self, actor_id: str) -> dict[str, Any] | None:
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        response = self._http.get(f"{self._api_base}/acts/{actor_id}", headers=headers)
        if response.status_code != 200:
            log.warning("Actor detail %s -> HTTP %d; its last update stays unknown", actor_id, response.status_code)
            return None
        payload = response.json()
        self._save(f"acts/{actor_id}.json", payload)
        return payload.get("data")

    def ideas_html(self) -> str | None:
        response = self._http.get(self._ideas_url)
        if response.status_code != 200:
            log.warning("Ideas page -> HTTP %d", response.status_code)
            return None
        self._save("ideas.html", response.text)
        return response.text

    def _save(self, relative: str, payload: Any) -> None:
        """Keep raw responses so they can be uploaded as a workflow artifact and become fixtures."""
        if self._raw_dir is None:
            return
        path = self._raw_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload, indent=1), encoding="utf-8")


class FixtureSource:
    """Serves tests/fixtures/apify/: store_actors.json, actor_details.json, ideas.html.

    store_actors.json holds Store items; this class filters and pages them the
    way the API does (category filter, popularity order, offset/limit).
    """

    def __init__(self, fixture_dir: Path) -> None:
        apify_dir = fixture_dir / "apify"
        self._items: list[dict[str, Any]] = json.loads((apify_dir / "store_actors.json").read_text(encoding="utf-8"))
        self._details: dict[str, Any] = json.loads((apify_dir / "actor_details.json").read_text(encoding="utf-8"))
        ideas_path = apify_dir / "ideas.html"
        self._ideas = ideas_path.read_text(encoding="utf-8") if ideas_path.exists() else None
        self.requests: list[tuple[str, Any]] = []

    def store_page(self, *, category: str | None, offset: int, limit: int, sort_by: str) -> dict[str, Any]:
        self.requests.append(("store", (category, offset, limit, sort_by)))
        items = [i for i in self._items if category is None or category in (i.get("categories") or [])]
        items.sort(key=lambda i: -int((i.get("stats") or {}).get("totalUsers30Days") or 0))
        page = items[offset : offset + limit]
        return {"total": len(items), "offset": offset, "limit": limit, "desc": False, "count": len(page), "items": page}

    def actor_detail(self, actor_id: str) -> dict[str, Any] | None:
        self.requests.append(("detail", actor_id))
        response = self._details.get(actor_id)
        return response.get("data") if response else None

    def ideas_html(self) -> str | None:
        self.requests.append(("ideas", None))
        return self._ideas
