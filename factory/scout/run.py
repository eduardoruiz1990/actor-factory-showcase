"""Scout pipeline: Store + Ideas -> niches -> 20 ranked candidates."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from factory.scout.ideas import parse_ideas_html
from factory.scout.models import ActorRecord, Candidate, Idea
from factory.scout.niches import Niche, attach_ideas, build_candidate, cluster_actors, rank
from factory.scout.sources import ScoutSource
from factory.scout.store import apply_actor_detail, parse_store_item

log = logging.getLogger(__name__)


@dataclass
class ScoutResult:
    collected_at: str
    candidates: list[Candidate]
    actors_seen: int = 0
    store_queries: int = 0
    niches_total: int = 0
    ideas_parsed: int = 0
    ideas_open: int = 0
    details_fetched: int = 0
    skipped_own_niches: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    watcher_summary: str | None = None  # Markdown from the latest Watcher run (Phase 3)

    def to_dict(self) -> dict[str, Any]:
        data = {k: v for k, v in self.__dict__.items() if k != "candidates"}
        data["candidates"] = [c.to_dict() for c in self.candidates]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoutResult":
        values = dict(data)
        values["candidates"] = [Candidate.from_dict(c) for c in data["candidates"]]
        return cls(**values)


def run_scout(source: ScoutSource, config: dict[str, Any], now: datetime) -> ScoutResult:
    scout_cfg = config["scout"]
    warnings: list[str] = []

    items, queries = fetch_store(source, scout_cfg["store"], warnings)
    actors = [parse_store_item(item, scout_cfg["failure_statuses"]) for item in items]

    ideas = fetch_ideas(source, config["apify"]["ideas_url"], warnings)
    open_statuses = set(scout_cfg["ideas"]["open_statuses"])

    clustering = scout_cfg["clustering"]
    if not all(isinstance(w, str) for w in clustering["stopwords"]):
        raise ValueError("scout.clustering.stopwords must all be quoted strings in config.yaml")
    stopwords = set(clustering["stopwords"])
    niches = cluster_actors(actors, stopwords, float(clustering["similarity_threshold"]))
    niches = attach_ideas(niches, ideas, stopwords, float(clustering["idea_match_threshold"]), open_statuses)

    # A niche where you already have an Actor is not a new opportunity.
    owner = (config.get("owner") or {}).get("apify_username") or ""
    skipped_own = [n.id for n in niches if owner and any(a.username == owner for a in n.actors)]
    niches = [n for n in niches if n.id not in skipped_own]

    min_demand = float(scout_cfg["ranking"]["min_demand"])
    first_pass = rank([c for c in (build_candidate(n, now, config) for n in niches) if c.demand >= min_demand])

    # The Store list has no update dates: look those up for the best niches only.
    details_cfg = scout_cfg["details"]
    pool_ids = {c.niche_id for c in first_pass[: int(details_cfg["niche_pool"])]}
    pool = [n for n in niches if n.id in pool_ids]
    fetched = fetch_details(source, pool, int(details_cfg["actors_per_niche"]), scout_cfg["failure_statuses"], warnings)

    final = rank([build_candidate(n, now, config) for n in pool])
    selected = final[: int(scout_cfg["candidates_per_week"])]
    if len(selected) < int(scout_cfg["candidates_per_week"]):
        warnings.append(f"Only {len(selected)} niches met the minimum demand of {min_demand:g}.")

    return ScoutResult(
        collected_at=now.isoformat(timespec="seconds"),
        candidates=selected,
        actors_seen=len(actors),
        store_queries=queries,
        niches_total=len(niches),
        ideas_parsed=len(ideas),
        ideas_open=sum(1 for i in ideas if i.status in open_statuses),
        details_fetched=fetched,
        skipped_own_niches=skipped_own,
        warnings=warnings,
    )


def fetch_store(source: ScoutSource, store_cfg: dict[str, Any], warnings: list[str]) -> tuple[list[dict[str, Any]], int]:
    """Run one Store query per category (plus one unfiltered) and merge by Actor id."""
    seen: dict[str, dict[str, Any]] = {}
    page_size = int(store_cfg["page_size"])
    max_items = int(store_cfg["max_items_per_query"])
    queries = [None, *store_cfg["categories"]]
    failed = 0
    for category in queries:
        offset = 0
        while offset < max_items:
            limit = min(page_size, max_items - offset)
            try:
                page = source.store_page(category=category, offset=offset, limit=limit, sort_by=store_cfg["sort_by"])
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                failed += 1
                warnings.append(f"Store query category={category or 'all'} offset={offset} failed: {exc}")
                break
            items = page.get("items") or []
            for item in items:
                if item.get("id"):
                    seen.setdefault(item["id"], item)
            # Items the API filters out still count towards the offset, so advance by `limit`.
            offset += limit
            if not items or offset >= int(page.get("total") or 0):
                break
    if failed == len(queries):
        raise RuntimeError("Every Store query failed; see warnings: " + "; ".join(warnings))
    return list(seen.values()), len(queries)


def fetch_ideas(source: ScoutSource, ideas_url: str, warnings: list[str]) -> list[Idea]:
    try:
        html = source.ideas_html()
    except httpx.HTTPError as exc:
        warnings.append(f"Ideas page could not be fetched: {exc}")
        return []
    if not html:
        warnings.append("Ideas page could not be fetched.")
        return []
    ideas = parse_ideas_html(html, ideas_url)
    if not ideas:
        warnings.append("Ideas page fetched but no ideas were parsed; the page layout may have changed.")
    return ideas


def fetch_details(
    source: ScoutSource, niches: list[Niche], per_niche: int, failure_statuses: list[str], warnings: list[str]
) -> int:
    fetched = 0
    failures = 0
    for niche in niches:
        for actor in niche.actors[:per_niche]:
            if _fill_detail(source, actor, failure_statuses):
                fetched += 1
            else:
                failures += 1
    if failures == 1:
        warnings.append("1 Actor detail lookup failed; that Actor counts as maintained.")
    elif failures:
        warnings.append(f"{failures} Actor detail lookups failed; those Actors count as maintained.")
    return fetched


def _fill_detail(source: ScoutSource, actor: ActorRecord, failure_statuses: list[str]) -> bool:
    try:
        detail = source.actor_detail(actor.id)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Actor detail %s failed: %s", actor.slug, exc)
        return False
    if not detail:
        return False
    apply_actor_detail(actor, detail, failure_statuses)
    return True
