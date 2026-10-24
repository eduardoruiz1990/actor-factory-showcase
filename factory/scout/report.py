"""Render the weekly Scout issue (title and Markdown body)."""

import json
from datetime import datetime, timezone
from typing import Any

from factory.scout.models import ActorSummary, Candidate
from factory.scout.run import ScoutResult

ISSUE_MARKER = "<!-- factory:scout v1 -->"
DATA_MARKER = "factory:scout-data"
MAX_BODY_CHARS = 60_000  # GitHub's limit is 65,536


def week_key(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def issue_title(result: ScoutResult, config: dict[str, Any]) -> str:
    week = week_key(datetime.fromisoformat(result.collected_at))
    return f"Scout {week}: {len(listed(result, config))} candidate niches"


def listed(result: ScoutResult, config: dict[str, Any]) -> list[Candidate]:
    """The candidates the issue shows: the first candidates_per_week in the result's order."""
    return result.candidates[: int(config["scout"]["candidates_per_week"])]


def render_issue_body(result: ScoutResult, config: dict[str, Any], verdicts: dict[str, str] | None = None) -> str:
    """`verdicts` maps niche_id to a short Validator result such as "5/5 PASS"."""
    week = week_key(datetime.fromisoformat(result.collected_at))
    shown = listed(result, config)
    if verdicts:
        intro = (f"The {len(shown)} best candidate niches after validation: candidates that pass all five checks "
                 "come first, then the rest by checks passed and opportunity score. The Validator's brief is in "
                 "the comments; its result is in the **Checks** column.")
    else:
        intro = (f"The top {len(shown)} of {len(result.candidates)} candidate niches from the Apify Store and Ideas "
                 f"page, by opportunity score. The Validator scores all {len(result.candidates)} on five checks, "
                 "then keeps the best here and posts a brief below.")
    lines = [
        ISSUE_MARKER,
        f"## Scout — week {week}",
        "",
        intro,
        "",
        f"**Data:** {result.actors_seen:,} Store Actors from {result.store_queries} queries · "
        f"{result.niches_total:,} niches, {result.niches_excluded:,} left out by `scout.exclude` · "
        f"{result.ideas_parsed} open ideas · "
        f"{result.details_fetched} Actor detail lookups · collected {_when(result.collected_at)}",
        "",
    ]
    if result.warnings:
        lines += ["> [!WARNING]", *[f"> {w}" for w in result.warnings], ""]

    header = "| # | Niche | Users 7d / 30d / 90d | Leader fail 30d | Leader rating | Days since update | Leader price | Maintained Actors | Open idea votes | Score |"
    divider = "|---|---|---|---|---|---|---|---|---|---|"
    if verdicts:
        header += " Checks |"
        divider += "---|"
    lines += [header, divider]
    for c in shown:
        row = (
            f"| {c.rank} | {_niche_link(c)} | {c.users_7d:,} / {c.users_30d:,} / {c.users_90d:,} "
            f"| {_pct(c.leader.failure_rate if c.leader else None)} | {_rating(c.leader)} "
            f"| {_days(c.leader)} | {c.leader.price_label if c.leader else 'no Actor yet'} "
            f"| {_maintained(c)} | {c.open_idea_upvotes or '—'} | {c.score:.2f} |"
        )
        if verdicts:
            row += f" {verdicts.get(c.niche_id, '—')} |"
        lines.append(row)

    lines += ["", "<details><summary>Niche details</summary>", ""]
    for c in shown:
        lines += _details(c)
    lines += ["</details>", ""]

    max_days = config["scout"]["maintained_max_days_since_update"]
    failure_statuses = " + ".join(config["scout"]["failure_statuses"])
    bonus = config["scout"]["ranking"]["weakness_bonus"]
    lines += [
        "**How to read this**",
        "- Users are summed across a niche's Actors, so one person using two Actors counts twice.",
        f"- Leader = the niche's Actor with the most users over 30 days. Failure rate = ({failure_statuses}) / all runs "
        "in the last 30 days, excluding the developer's own runs.",
        f"- Maintained = latest build within {max_days} days and not under maintenance. Actors whose build date "
        "is unknown count as maintained (marked +).",
        f"- Score = log10(1 + demand) × (1 + {bonus} × competition gaps), where demand is 30-day users or open-idea "
        "upvotes weighted per config.yaml, whichever is larger.",
        "",
        "**Watcher summary**",
        result.watcher_summary.strip() if result.watcher_summary
        else "_No Watcher summary yet (the Watcher arrives in Phase 3)._",
        "",
    ]
    if result.skipped_own_niches:
        lines += [f"Skipped niches where you already have an Actor: {', '.join(result.skipped_own_niches)}", ""]

    body = "\n".join(lines)
    data = _hidden_data(result, include_alternatives=True)
    if len(body) + len(data) > MAX_BODY_CHARS:
        data = _hidden_data(result, include_alternatives=False)
    return body + "\n" + data + "\n"


def parse_hidden_data(body: str) -> dict[str, Any] | None:
    start = body.find(f"<!-- {DATA_MARKER} ")
    if start < 0:
        return None
    end = body.find(" -->", start)
    return json.loads(body[start + len(DATA_MARKER) + 6 : end])


def _hidden_data(result: ScoutResult, include_alternatives: bool) -> str:
    data = result.to_dict()
    if not include_alternatives:
        for candidate in data["candidates"]:
            candidate["alternatives"] = []
    # Escape ">" so the JSON can never close the HTML comment early.
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True).replace(">", "\\u003e")
    return f"<!-- {DATA_MARKER} {payload} -->"


def _niche_link(c: Candidate) -> str:
    url = c.leader.url if c.leader else (c.ideas[0].url if c.ideas else "")
    label = _plain(c.label)
    return f"[{label}]({url}) `{c.niche_id}`" if url else f"{label} `{c.niche_id}`"


def _details(c: Candidate) -> list[str]:
    lines = [f"#### {c.rank}. {_plain(c.label)} — `{c.niche_id}`"]
    if c.leader:
        lines.append(f"- Leader: {_actor_line(c.leader)}")
    else:
        lines.append("- No Store Actor yet: this niche comes from the Ideas page.")
    if c.alternatives:
        more = c.actor_count - 1 - len(c.alternatives)
        lines.append(f"- Other Actors ({c.actor_count - 1}):")
        lines += [f"  - {_actor_line(a)}" for a in c.alternatives]
        if more > 0:
            lines.append(f"  - …and {more} more")
    for idea in c.ideas:
        lines.append(f"- Idea: [{_plain(idea.title)}]({idea.url}) — {idea.upvotes} upvotes ({idea.status or 'status unknown'})")
    if c.weaknesses:
        lines.append(f"- Competition gaps: {'; '.join(c.weaknesses)}")
    lines.append("")
    return lines


def _actor_line(a: ActorSummary) -> str:
    parts = [f"[{_plain(a.slug)}]({a.url})", f"{a.users_30d:,} users/30d"]
    if a.failure_rate is not None:
        parts.append(f"fails {_pct(a.failure_rate)} of {a.runs_30d_total:,} runs")
    parts.append(f"rating {a.rating:.1f} ({a.review_count})" if a.rating is not None else "unrated")
    parts.append(f"updated {a.days_since_update} days ago" if a.days_since_update is not None else "update date unknown")
    parts.append(_plain(a.price_label))
    return " · ".join(parts)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def _rating(leader: ActorSummary | None) -> str:
    if leader is None or leader.rating is None:
        return "—"
    return f"{leader.rating:.1f} ({leader.review_count})"


def _days(leader: ActorSummary | None) -> str:
    if leader is None or leader.days_since_update is None:
        return "—"
    return str(leader.days_since_update)


def _plain(text: str) -> str:
    """Third-party text in a table cell or link label: no pipes, brackets or line breaks."""
    return " ".join(text.replace("|", "/").replace("[", "(").replace("]", ")").split())


def _maintained(c: Candidate) -> str:
    if c.actor_count == 0:
        return "none"
    return f"{c.maintained_alternatives}{'+' if c.maintained_unknown else ''} of {c.actor_count}"


def _when(iso: str) -> str:
    moment = datetime.fromisoformat(iso)
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%d %H:%M UTC")
