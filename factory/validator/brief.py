"""Render the Validator's one-page brief (posted as a comment on the weekly issue)."""

import json
from typing import Any

from factory.validator.checks import CHECK_NAMES, FAIL, PASS
from factory.validator.run import Validation

BRIEF_MARKER = "<!-- factory:validator v1 -->"
DATA_MARKER = "factory:validator-data"
HARD_FAILS_MARKER = "factory:validator-hard-fails"
ASSESSED_MARKER = "factory:validator-assessed"
ICONS = {PASS: "✅", FAIL: "❌"}
UNKNOWN_ICON = "❔"
REVIEW_ICON = "🔎"
VERDICT_LABELS = {"PASS": "✅ PASS", "REVIEW": f"{REVIEW_ICON} REVIEW"}
DETAILED_PICKS = 3
MAX_BODY_CHARS = 60_000  # GitHub's limit is 65,536
ALL, BUILDABLE, NONE = "all", "buildable", "none"  # which assessments the hidden data keeps


def verdict_labels(validations: list[Validation]) -> dict[str, str]:
    """Short results for the Checks column of the weekly issue."""
    return {
        v.candidate.niche_id: f"{v.passed}/{len(v.checks)} {VERDICT_LABELS.get(v.verdict, '❌')}"
        for v in validations
    }


def render_brief(
    validations: list[Validation], config: dict[str, Any], run: str, assessed: int | None = None,
    blocked: dict[str, dict[str, str]] | None = None, newly_blocked: int = 0, assessed_ids: list[str] | None = None,
) -> str:
    """`validations` are the candidates the issue lists; `assessed` is how many were validated in all.

    `blocked` holds every niche Scout should keep skipping (Q18), `newly_blocked` how many of them are new.
    `assessed_ids` are all the niches validated in this run, which Scout skips for a few weeks (Q20).
    """
    # Passing candidates keep Scout's order (opportunity score).
    passing = sorted((v for v in validations if v.verdict == "PASS"), key=lambda v: v.candidate.rank)
    review = sorted((v for v in validations if v.verdict == "REVIEW"), key=lambda v: v.candidate.rank)
    failing = [v for v in validations if v.verdict == "FAIL"]
    model = config["validator"]["model"]
    served = sorted({v.assessment.model for v in validations if v.assessment and v.assessment.model})

    lines = [
        BRIEF_MARKER,
        f"## Validator brief — {run}",
        "",
        f"**{len(passing)} of {len(validations)} listed candidates pass all five checks"
        + (f", {len(review)} need{'s' if len(review) == 1 else ''} your review of {'its' if len(review) == 1 else 'their'} terms"
           if review else "")
        + "**"
        + (f" ({assessed} assessed; the issue lists the best {len(validations)})" if assessed and assessed > len(validations) else "")
        + ". "
        f"Facts assessed by `{model}`"
        + (f" (served by {', '.join(f'`{m}`' for m in served)})" if served and served != [model] else "")
        + "; pass/fail decided by the thresholds in `config.yaml`. "
        f"{ICONS[PASS]} pass · {ICONS[FAIL]} fail · {UNKNOWN_ICON} unknown (counts as a fail) · "
        f"{REVIEW_ICON} REVIEW: only unclear terms are open",
        "",
        "| # | Niche | Demand | Competition | Legality | Cost | Stability | Result |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for v in sorted(validations, key=lambda v: v.candidate.rank):
        icons = " | ".join(ICONS.get(v.check(name).status, UNKNOWN_ICON) for name in CHECK_NAMES)
        result = {"PASS": "**PASS**", "REVIEW": f"{REVIEW_ICON} **REVIEW**"}.get(v.verdict, f"{v.passed}/5")
        lines.append(f"| {v.candidate.rank} | {_plain(v.candidate.label)} | {icons} | {result} |")
    lines.append("")

    if passing:
        lines += ["### Best picks", ""]
        for v in passing[:DETAILED_PICKS]:
            lines += _pick(v)
        if len(passing) > DETAILED_PICKS:
            others = ", ".join(f"#{v.candidate.rank} {v.candidate.label}" for v in passing[DETAILED_PICKS:])
            lines += [f"Also passing: {others}.", ""]
    else:
        lines += ["### Best picks", "", "None this week: no candidate passed all five checks.", ""]

    if review:
        lines += [
            f"### {REVIEW_ICON} Needs your review: terms",
            "",
            "Clean on everything else: official API or public feed, no login, no personal data the Actor cannot "
            "strip, robots.txt allows it. The terms neither forbid automated reuse nor clearly allow it. Read them; "
            "if you are satisfied, comment the command shown (Q17).",
            "",
        ]
        for v in review:
            a = v.assessment
            lines.append(f"- **#{v.candidate.rank} {v.candidate.label}** ({a.target_domain}): {v.review_reason}")
            if a.terms_source_url:
                quote = " ".join(a.terms_quote.split()).replace("|", "/")
                lines.append(f"  - Closest passage: “{quote}” ([source]({a.terms_source_url}))" if quote
                             else f"  - Page read: {a.terms_source_url}")
            lines.append(f"  - To build after reviewing: `/build {v.candidate.niche_id} terms-reviewed`")
        lines.append("")

    if failing:
        lines += ["### Why the others did not pass", ""]
        for v in sorted(failing, key=lambda v: v.candidate.rank):
            reasons = "; ".join(f"{c.name.capitalize()}: {c.short}" for c in v.checks if c.status != PASS)
            lines.append(f"- **#{v.candidate.rank} {v.candidate.label}** — {reasons}")
        lines.append("")

    if newly_blocked:
        weeks = config["scout"]["history"]["skip_hard_fails_weeks"]
        lines += [
            f"{newly_blocked} of the assessed niches failed Legality for a reason no build can fix (login, personal "
            f"data as the product, terms that forbid the use, or robots.txt). Scout skips them for {weeks} weeks.",
            "",
        ]

    lines += [
        "**Decision for you:** to build a candidate, add the `go` label to this issue, then comment "
        "`/build <niche-id>` (or `/build <niche-id> terms-reviewed` for a 🔎 REVIEW candidate). "
        "The Builder opens a pull request; nothing merges without you.",
        "",
    ]
    body = "\n".join(lines)
    if blocked:
        body += _hidden_json(HARD_FAILS_MARKER, blocked)  # small, and Scout needs it: never dropped
    if assessed_ids:
        body += _hidden_json(ASSESSED_MARKER, sorted(set(assessed_ids)))  # small, and Scout needs it: never dropped
    # The Builder needs the assessments of PASS and REVIEW candidates, so those are dropped last.
    for keep in (ALL, BUILDABLE, NONE):
        data = _hidden_data(validations, keep)
        if len(body) + len(data) <= MAX_BODY_CHARS:
            break
    else:
        data = ""  # the visible brief matters more than the machine copy
    return body + data + "\n"


def _pick(v: Validation) -> list[str]:
    a = v.assessment
    c = v.candidate
    header = f"**#{c.rank} {c.label}**"
    if a:
        where = a.target_domain or ("tool" if a.kind == "tool" else "no target site")
        if a.kind == "tool" and a.target_domain:
            where = f"tool using {a.target_domain}"
        header += f" — proposed Actor `{a.proposed_actor_name}` ({where}, confidence {a.confidence})"
    lines = [header, ""]
    if a:
        lines += [a.pitch, "", f"Output: {', '.join(a.output_fields)}.", ""]
    lines += [f"- {check.name.capitalize()}: {check.reason}" for check in v.checks]
    if a and a.terms_quote and a.terms_source_url:
        quote = " ".join(a.terms_quote.split()).replace("|", "/")
        lines.append(f"- Terms: “{quote}” ([source]({a.terms_source_url}))")
    if a and a.risks:
        lines.append(f"- Risks: {'; '.join(a.risks)}")
    lines.append("")
    return lines


def _plain(text: str) -> str:
    return " ".join(text.replace("|", "/").replace("[", "(").replace("]", ")").split())


def parse_hidden_data(body: str) -> list[dict[str, Any]] | None:
    start = body.find(f"<!-- {DATA_MARKER} ")
    if start < 0:
        return None
    end = body.find(" -->", start)
    return json.loads(body[start + len(DATA_MARKER) + 6 : end])


def _hidden_data(validations: list[Validation], keep: str = ALL) -> str:
    """The machine copy of the listed validations, with all, only the buildable, or no assessments."""
    records = [v.to_dict() for v in validations]
    for record in records:
        if keep == NONE or (keep == BUILDABLE and record["verdict"] not in VERDICT_LABELS):
            record["assessment"] = None
    return _hidden_json(DATA_MARKER, records)


def _hidden_json(marker: str, value: Any) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True)
    # Escape ">" so the JSON can never close the HTML comment early.
    return f"<!-- {marker} {payload.replace('>', '\\u003e')} -->"
