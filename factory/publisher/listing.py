"""Find the Actors a merge changed and prepare their Store listing text.

The Publisher workflow deploys each changed Actor with `apify push`; this
module turns the Actor's files into the text and the monetization values the
owner enters once in Apify Console before clicking Publish (QUESTIONS Q14).
"""

import json
from pathlib import Path
from typing import Any

SEO_TITLE_MAX = 60
SEO_DESCRIPTION_MAX = 155


def changed_actors(files: list[str], repo_root: Path) -> list[str]:
    """Names of actors/<name>/ folders touched by `files` that still hold an Actor definition."""
    names = sorted({f.split("/")[1] for f in files if f.startswith("actors/") and f.count("/") >= 2})
    return [n for n in names if (repo_root / "actors" / n / ".actor" / "actor.json").exists()]


def load_actor(actor_dir: Path) -> dict[str, Any]:
    actor_json = json.loads((actor_dir / ".actor" / "actor.json").read_text(encoding="utf-8"))
    pricing = json.loads((actor_dir / ".actor" / "pricing.json").read_text(encoding="utf-8"))
    listing_path = actor_dir / ".actor" / "listing.json"
    listing = json.loads(listing_path.read_text(encoding="utf-8")) if listing_path.exists() else {}
    return {"actor": actor_json, "pricing": pricing, "listing": listing}


def render_listing(name: str, owner: str, data: dict[str, Any], build_url: str | None = None) -> str:
    actor, pricing, listing = data["actor"], data["pricing"], data["listing"]
    title = actor.get("title") or name
    description = actor.get("description") or ""
    seo_title = (listing.get("seoTitle") or title)[:SEO_TITLE_MAX]
    seo_description = (listing.get("seoDescription") or description)[:SEO_DESCRIPTION_MAX]
    categories = ", ".join(listing.get("categories") or []) or "choose one or two"
    console = f"https://console.apify.com/actors/{owner}~{name}" if owner else "https://console.apify.com/actors"

    lines = [
        f"<!-- factory:publisher {name} -->",
        f"## Publish `{name}`",
        "",
        f"`apify push` deployed the merged code{f' ([build]({build_url}))' if build_url else ''}. "
        "The Actor stays private until you publish it. In "
        f"[Apify Console]({console}), on the Actor's **Publishing** tab:",
        "",
        "**1. Store listing** (copy and paste)",
        "",
        f"- Title: `{title}`",
        f"- Description: `{description}`",
        f"- SEO title ({len(seo_title)}/{SEO_TITLE_MAX}): `{seo_title}`",
        f"- SEO description ({len(seo_description)}/{SEO_DESCRIPTION_MAX}): `{seo_description}`",
        f"- Categories: {categories}",
        "",
        "**2. Monetization** → Set up monetization → pay per event:",
        "",
        "| Event | Title | Price | Primary |",
        "|---|---|---|---|",
    ]
    for event, spec in pricing.get("events", {}).items():
        if "pricePer1000Usd" in spec:
            per_event = spec["pricePer1000Usd"] / 1000
            price = f"${per_event:.6f}".rstrip("0").rstrip(".") + f" per event (${spec['pricePer1000Usd']:.2f} per 1,000)"
        else:
            price = "keep Apify's default"
        lines.append(f"| `{event}` | {spec.get('title', '')} | {price} | {'yes' if spec.get('isPrimary') else ''} |")
    lines += [
        "",
        f"- Minimum max cost per run: ${pricing.get('minimalMaxTotalChargeUsd', 0.5):.2f}",
        f"- Pass platform usage costs to users: {'yes' if pricing.get('platformUsagePaidByUser') else 'no'}",
        "- Do not add another per-result event: results are charged by `apify-default-dataset-item`.",
        "",
        "**3. Publish**: check the README preview, run the Actor once from Console, then click **Publish**.",
        "",
        "Close this issue once the Actor is public.",
    ]
    return "\n".join(lines) + "\n"
