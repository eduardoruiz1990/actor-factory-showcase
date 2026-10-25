"""The five Validator checks. Thresholds come from config.yaml (validator section).

Demand and Competition use Scout's numbers only. Legality, Cost and Stability
use the model's assessment plus a live robots.txt check. A check that cannot
be decided is "unknown", and unknown never counts as a pass.
"""

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit

from factory.scout.models import Candidate
from factory.validator.assessment import Assessment
from factory.validator.robots import RobotsResult

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"
CHECK_NAMES = ("demand", "competition", "legality", "cost", "stability")
ACCESS_LABELS = {"official_api": "official API", "public_feed": "public feed", "public_html": "public pages"}


@dataclass
class CheckResult:
    name: str
    status: str
    reason: str
    short: str = ""  # a few words for the one-line summaries; defaults to the reason

    def __post_init__(self) -> None:
        if not self.short:
            self.short = self.reason

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _usd(amount: float) -> str:
    return f"${amount:,.2f}" if amount >= 0.1 else f"${amount:.3f}"


def check_demand(c: Candidate, cfg: dict[str, Any]) -> CheckResult:
    min_users = int(cfg["min_users_30d"])
    min_upvotes = int(cfg["min_idea_upvotes"])
    if c.users_30d >= min_users:
        return CheckResult(
            "demand", PASS, f"{c.users_30d:,} users in 30 days across {_plural(c.actor_count, 'Actor')} (≥ {min_users})"
        )
    if c.open_idea_upvotes >= min_upvotes:
        return CheckResult("demand", PASS, f"open idea with {c.open_idea_upvotes} upvotes (≥ {min_upvotes})")
    return CheckResult(
        "demand", FAIL,
        f"{c.users_30d:,} users in 30 days (< {min_users}) and no open idea with ≥ {_plural(min_upvotes, 'upvote')}",
        short=f"{c.users_30d:,} users in 30 days, no open idea",
    )


def check_competition(c: Candidate, cfg: dict[str, Any]) -> CheckResult:
    fewer_than = int(cfg["fewer_than_maintained_alternatives"])
    fail_above = float(cfg["leader_failure_rate_above"])
    rating_below = float(cfg["leader_rating_below"])
    plus = "+" if c.maintained_unknown else ""
    if c.maintained_alternatives < fewer_than:
        count = c.maintained_alternatives
        label = "no maintained alternative" if count == 0 else _plural(count, "maintained alternative")
        return CheckResult("competition", PASS, f"{label} (< {fewer_than})")
    leader = c.leader
    if leader and leader.failure_rate is not None and leader.failure_rate > fail_above:
        return CheckResult("competition", PASS, f"leader fails {leader.failure_rate:.1%} of runs (> {fail_above:.0%})")
    if leader and leader.rating is not None and leader.rating < rating_below:
        return CheckResult("competition", PASS, f"leader is rated {leader.rating:.1f} (< {rating_below:g})")
    leader_note = ""
    if leader:
        fail = "unknown" if leader.failure_rate is None else f"{leader.failure_rate:.1%}"
        rating = "unrated" if leader.rating is None else f"rated {leader.rating:.1f}"
        leader_note = f"; leader fails {fail} of runs, {rating}"
    return CheckResult(
        "competition", FAIL, f"{c.maintained_alternatives}{plus} maintained alternatives{leader_note}",
        short=f"{c.maintained_alternatives}{plus} maintained alternatives and a strong leader",
    )


# Legality failures that no change on our side can fix. Scout skips niches that failed with one of
# these for scout.history.skip_hard_fails_weeks (Q18).
NEEDS_LOGIN = "needs a login"
CORE_PERSONAL_DATA = "the data is personal data"
TERMS_FORBID = "terms forbid automated access or reuse"
ROBOTS_DISALLOW = "robots.txt disallows"
HARD_LEGALITY_FAILS = (NEEDS_LOGIN, CORE_PERSONAL_DATA, TERMS_FORBID, ROBOTS_DISALLOW)


def hard_legality_fail(reason: str) -> str | None:
    """The first hard failure named in a Legality reason, or None."""
    for part in reason.split("; "):
        if part.startswith(HARD_LEGALITY_FAILS):
            return part
    return None


def check_legality(a: Assessment | None, robots: RobotsResult | None, cfg: dict[str, Any]) -> CheckResult:
    if a is None:
        return CheckResult("legality", UNKNOWN, "no assessment")
    fails: list[str] = []
    unknowns: list[str] = []
    # Hard rules: data behind a login, or personal data that is the value itself, never passes.
    # Personal data the Actor can strip passes only when the owner allows it (Q6).
    if a.login_required == "yes" or a.data_access == "requires_login":
        fails.append(NEEDS_LOGIN)
    elif a.login_required != "no":
        unknowns.append("login requirement unclear")
    if a.personal_data == "core":
        fails.append(CORE_PERSONAL_DATA)
    elif a.personal_data == "removable" and not cfg["allow_removable_personal_data"]:
        fails.append("the source mixes in personal data")
    elif a.personal_data == "unclear":
        unknowns.append("personal data unclear")
    if a.terms_allow_automated_access == "no":
        fails.append(TERMS_FORBID)
    elif a.terms_allow_automated_access != "yes":
        unknowns.append("terms unclear")
    elif cfg["require_terms_source"] and not (_is_http_url(a.terms_source_url) and a.terms_quote.strip()):
        unknowns.append("terms said to allow it, but no source page and quote were given")
    if a.data_access == "unknown":
        unknowns.append("access method unknown")
    if robots is None or robots.allowed is None:
        unknowns.append(robots.detail if robots else "robots.txt not checked")
    elif robots.allowed is False:
        fails.append(robots.detail)
    if fails:
        return CheckResult("legality", FAIL, "; ".join(fails + unknowns), short="; ".join(fails[:2]))
    if unknowns:
        return CheckResult("legality", UNKNOWN, "; ".join(unknowns))
    access = ACCESS_LABELS.get(a.data_access, a.data_access)
    source = f" ({urlsplit(a.terms_source_url).netloc})" if _is_http_url(a.terms_source_url) else ""
    personal = "personal data stripped by the Actor" if a.personal_data == "removable" else "no personal data"
    return CheckResult(
        "legality", PASS,
        f"{access}, no login, {personal}, terms allow it{source}; {robots.detail}",
    )


def _is_http_url(value: str) -> bool:
    parts = urlsplit(value or "")
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def check_cost(c: Candidate, a: Assessment | None, cfg: dict[str, Any], apify_cfg: dict[str, Any]) -> CheckResult:
    if a is None:
        return CheckResult("cost", UNKNOWN, "no assessment")
    floors = cfg["min_compute_units_per_1000"]
    compute_units = max(a.compute_units_per_1000_results, float(floors[a.approach]))
    proxy_gb = 0.0
    if a.proxy == "residential":
        proxy_gb = max(a.residential_gb_per_1000_results, float(cfg["min_residential_gb_per_1000"]))
    cost = compute_units * float(apify_cfg["compute_unit_usd"]) + proxy_gb * float(apify_cfg["residential_proxy_usd_per_gb"])

    planned, basis = planned_price_per_1000(c, cfg)
    share = cost / planned
    limit = float(cfg["max_share_of_price"])
    usage = f"{compute_units:.2f} CU" + (f" + {proxy_gb:.2f} GB residential proxy" if proxy_gb else "")
    reason = (
        f"~{_usd(cost)} platform cost per 1,000 results ({usage}) is {share:.1%} of the planned "
        f"{_usd(planned)} ({basis}); limit {limit:.0%}"
    )
    short = f"platform cost {share:.0%} of the planned {_usd(planned)} per 1,000 results"
    return CheckResult("cost", PASS if share < limit else FAIL, reason, short=short)


def planned_price_per_1000(c: Candidate, cfg: dict[str, Any]) -> tuple[float, str]:
    """The price per 1,000 results a new Actor would charge in this niche, and how it was chosen (Q5)."""
    leader_price = c.leader.price_per_1000_usd if c.leader else None
    if leader_price:
        share_of_leader = float(cfg["planned_price_share_of_leader"])
        return leader_price * share_of_leader, f"{share_of_leader:.0%} of the leader's ${leader_price:.2f}"
    basis = "default price; the leader is free or unpriced" if c.leader else "default price"
    return float(cfg["default_price_per_1000_usd"]), basis


def check_stability(a: Assessment | None, cfg: dict[str, Any]) -> CheckResult:
    if a is None:
        return CheckResult("stability", UNKNOWN, "no assessment")
    if a.official_api_or_feed:
        return CheckResult("stability", PASS, f"official API or feed ({a.target_domain})")
    if a.layout_change_frequency in cfg["passing_layout_change"]:
        return CheckResult("stability", PASS, f"layout rarely changes: {a.stability_notes}")
    if a.layout_change_frequency == "unknown":
        return CheckResult("stability", UNKNOWN, "layout change frequency unknown")
    return CheckResult(
        "stability", FAIL, f"no official API; layout changes {a.layout_change_frequency}ly: {a.stability_notes}",
        short=f"no official API, layout changes {a.layout_change_frequency}ly",
    )


def terms_review_reason(a: Assessment | None, robots: RobotsResult | None, cfg: dict[str, Any]) -> str | None:
    """Why a candidate needs the owner's review of its terms, or None when it does not qualify (Q17).

    It qualifies only when unclear terms are the sole open point: an official API or public feed, no
    login, no personal data (or only data the Actor strips, when Q6 allows it), robots.txt allowing the
    sample URLs, and terms that neither forbid
    the use nor were shown to allow it with a cited source.
    """
    if not cfg.get("review_unclear_terms") or a is None:
        return None
    personal_ok = ("none", "removable") if cfg["allow_removable_personal_data"] else ("none",)
    if a.data_access not in cfg["review_access"] or a.login_required != "no" or a.personal_data not in personal_ok:
        return None
    if robots is None or robots.allowed is not True:
        return None
    sourced_yes = a.terms_allow_automated_access == "yes" and _is_http_url(a.terms_source_url) and a.terms_quote.strip()
    if a.terms_allow_automated_access == "no" or sourced_yes:
        return None
    return a.terms_notes or "the terms do not settle commercial reuse"


def evaluate(
    c: Candidate, a: Assessment | None, robots: RobotsResult | None, config: dict[str, Any]
) -> list[CheckResult]:
    v = config["validator"]
    return [
        check_demand(c, v["demand"]),
        check_competition(c, v["competition"]),
        check_legality(a, robots, v["legality"]),
        check_cost(c, a, v["cost"], config["apify"]),
        check_stability(a, v["stability"]),
    ]
