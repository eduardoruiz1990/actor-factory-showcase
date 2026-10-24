"""Render the Validator's one-page brief (posted as a comment on the weekly issue)."""

import json
from typing import Any

from factory.validator.checks import CHECK_NAMES, FAIL, PASS
from factory.validator.run import Validation

BRIEF_MARKER = "<!-- factory:validator v1 -->"
DATA_MARKER = "factory:validator-data"
ICONS = {PASS: "✅", FAIL: "❌"}
UNKNOWN_ICON = "❔"
DETAILED_PICKS = 3
MAX_BODY_CHARS = 60_000  # GitHub's limit is 65,536


def verdict_labels(validations: list[Validation]) -> dict[str, str]:
    """Short results for the Checks column of the weekly issue."""
    return {
        v.candidate.niche_id: f"{v.passed}/{len(v.checks)} {'✅ PASS' if v.verdict == 'PASS' else '❌'}"
        for v in validations
    }


def render_brief(validations: list[Validation], config: dict[str, Any], week: str, assessed: int | None = None) -> str:
    """`validations` are the candidates the issue lists; `assessed` is how many were validated in all."""
    # Passing candidates keep Scout's order (opportunity score).
    passing = sorted((v for v in validations if v.verdict == "PASS"), key=lambda v: v.candidate.rank)
    failing = [v for v in validations if v.verdict != "PASS"]
    model = config["validator"]["model"]
    served = sorted({v.assessment.model for v in validations if v.assessment and v.assessment.model})

    lines = [
        BRIEF_MARKER,
        f"## Validator brief — week {week}",
        "",
        f"**{len(passing)} of {len(validations)} listed candidates pass all five checks**"
        + (f" ({assessed} assessed; the issue lists the best {len(validations)})" if assessed and assessed > len(validations) else "")
        + ". "
        f"Facts assessed by `{model}`"
        + (f" (served by {', '.join(f'`{m}`' for m in served)})" if served and served != [model] else "")
        + "; pass/fail decided by the thresholds in `config.yaml`. "
        f"{ICONS[PASS]} pass · {ICONS[FAIL]} fail · {UNKNOWN_ICON} unknown (counts as a fail)",
        "",
        "| # | Niche | Demand | Competition | Legality | Cost | Stability | Result |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for v in sorted(validations, key=lambda v: v.candidate.rank):
        icons = " | ".join(ICONS.get(v.check(name).status, UNKNOWN_ICON) for name in CHECK_NAMES)
        result = "**PASS**" if v.verdict == "PASS" else f"{v.passed}/5"
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

    if failing:
        lines += ["### Why the others did not pass", ""]
        for v in sorted(failing, key=lambda v: v.candidate.rank):
            reasons = "; ".join(f"{c.name.capitalize()}: {c.short}" for c in v.checks if c.status != PASS)
            lines.append(f"- **#{v.candidate.rank} {v.candidate.label}** — {reasons}")
        lines.append("")

    lines += [
        "**Decision for you:** add the `go` label to this issue to build a passing candidate. "
        "The Builder arrives in Phase 2; until then the label does nothing (see docs/QUESTIONS.md Q1).",
        "",
    ]
    body = "\n".join(lines)
    data = _hidden_data(validations, with_assessments=True)
    if len(body) + len(data) > MAX_BODY_CHARS:
        data = _hidden_data(validations, with_assessments=False)
    return body + data + "\n"


def _pick(v: Validation) -> list[str]:
    a = v.assessment
    c = v.candidate
    header = f"**#{c.rank} {c.label}**"
    if a:
        header += f" — proposed Actor `{a.proposed_actor_name}` ({a.target_domain}, confidence {a.confidence})"
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


def _hidden_data(validations: list[Validation], with_assessments: bool) -> str:
    records = [v.to_dict() for v in validations]
    if not with_assessments:
        for record in records:
            record["assessment"] = None
    payload = json.dumps(records, separators=(",", ":"), sort_keys=True)
    # Escape ">" so the JSON can never close the HTML comment early.
    return f"<!-- {DATA_MARKER} {payload.replace('>', '\\u003e')} -->"
