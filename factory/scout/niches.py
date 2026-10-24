"""Group Store Actors into niches, attach ideas, and score each niche.

A niche is a set of Actors whose titles share keywords (the leader's keywords
define the niche), plus any Ideas-page entries that match it. Open ideas with
no matching Actor become niches of their own.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from factory.scout.models import ActorRecord, ActorSummary, Candidate, Idea

WORD = re.compile(r"[a-z0-9]+")
# Words ending in "s" that are not plurals.
KEEP_S = frozenset({"news", "series", "species", "lens", "gas", "ios", "macos", "aws", "sms", "dns", "https"})


# Store titles often add a sales tail after a separator ("Tweet Scraper V2 - X Scraper / Twitter Scraper",
# "LinkedIn Profile Scraper (No Cookies)"); the niche is named before it.
TITLE_TAIL = re.compile(r"\s[-–—|:/+]\s|[|(\[:]|\s[-–—]")


def title_core(title: str) -> str:
    return TITLE_TAIL.split(title, maxsplit=1)[0]


def keywords(title: str, stopwords: set[str]) -> tuple[str, ...]:
    """Words that describe the niche, singular, in title order, without duplicates.

    Only the part of the title before its first separator counts, unless that part has no such words.
    """
    return _keywords(title_core(title), stopwords) or _keywords(title, stopwords)


def _keywords(text: str, stopwords: set[str]) -> tuple[str, ...]:
    words: list[str] = []
    for word in WORD.findall(text.lower()):
        if word in stopwords or word.isdigit():
            continue
        word = _singular(word)
        if word not in stopwords and word not in words:
            words.append(word)
    return tuple(words)


def _singular(word: str) -> str:
    """Light singularisation so "jobs" matches "job" and "opportunities" matches "opportunity"."""
    if len(word) < 4 or word in KEEP_S or word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "xes")):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    left, right = set(a), set(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


@dataclass
class Niche:
    keywords: tuple[str, ...]  # the founding Actor's (or idea's) keywords
    actors: list[ActorRecord] = field(default_factory=list)  # sorted: leader first
    ideas: list[Idea] = field(default_factory=list)

    @property
    def id(self) -> str:
        return "-".join(self.keywords)

    @property
    def leader(self) -> ActorRecord | None:
        return self.actors[0] if self.actors else None

    @property
    def label(self) -> str:
        if self.leader:
            return self.leader.title
        return self.ideas[0].title if self.ideas else self.id


def cluster_actors(actors: list[ActorRecord], stopwords: set[str], threshold: float) -> list[Niche]:
    """Greedy clustering: the most-used Actor founds a niche, others join the closest one."""
    niches: list[Niche] = []
    for actor in sorted(actors, key=lambda a: (-a.users_30d, a.slug)):
        words = keywords(actor.title, stopwords)
        if not words:
            continue
        best, best_score = None, 0.0
        for niche in niches:
            score = jaccard(words, niche.keywords)
            if score > best_score:
                best, best_score = niche, score
        if best is not None and best_score >= threshold:
            best.actors.append(actor)
        else:
            niches.append(Niche(keywords=words, actors=[actor]))
    return niches


def attach_ideas(
    niches: list[Niche], ideas: list[Idea], stopwords: set[str], threshold: float, open_statuses: set[str]
) -> list[Niche]:
    """Attach each idea to its best-matching niche; open unmatched ideas become niches."""
    result = list(niches)
    for idea in ideas:
        words = keywords(idea.title, stopwords)
        if not words:
            continue
        best, best_score = None, 0.0
        for niche in result:
            score = jaccard(words, niche.keywords)
            if score > best_score:
                best, best_score = niche, score
        if best is not None and best_score >= threshold:
            best.ideas.append(idea)
        elif idea.status in open_statuses:
            result.append(Niche(keywords=words, ideas=[idea]))
    return result


def is_excluded(niche: Niche, exclude_cfg: dict[str, Any]) -> bool:
    """True when the niche can never pass: a listed title word, or a leader in a listed category."""
    if set(niche.keywords) & set(exclude_cfg["title_words"]):
        return True
    return bool(niche.leader and set(niche.leader.categories) & set(exclude_cfg["categories"]))


def days_since(iso: str | None, now: datetime) -> int | None:
    if not iso:
        return None
    when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max((now - when).days, 0)


def is_maintained(actor: ActorRecord, now: datetime, max_days: int) -> bool | None:
    """True/False when the build date is known; None when it is not."""
    if actor.is_deprecated or actor.notice == "UNDER_MAINTENANCE":
        return False
    age = days_since(actor.last_build_at, now)
    if age is None:
        return None
    return age <= max_days


def summarise_actor(actor: ActorRecord, now: datetime, max_days: int) -> ActorSummary:
    return ActorSummary(
        slug=actor.slug,
        title=actor.title,
        url=actor.url,
        users_30d=actor.users_30d,
        failure_rate=actor.failure_rate,
        runs_30d_total=actor.runs_30d_total,
        rating=actor.rating,
        review_count=actor.review_count,
        days_since_update=days_since(actor.last_build_at, now),
        price_per_1000_usd=actor.price_per_1000_usd,
        price_label=actor.price_label,
        pricing_model=actor.pricing_model,
        maintained=is_maintained(actor, now, max_days),
    )


def build_candidate(niche: Niche, now: datetime, config: dict[str, Any]) -> Candidate:
    scout_cfg = config["scout"]
    competition = config["validator"]["competition"]
    max_days = int(scout_cfg["maintained_max_days_since_update"])
    open_statuses = set(scout_cfg["ideas"]["open_statuses"])

    summaries = [summarise_actor(a, now, max_days) for a in niche.actors]
    leader = summaries[0] if summaries else None
    # Unknown build date counts as maintained: that can only make competition look stronger.
    maintained = sum(1 for s in summaries if s.maintained is not False)
    maintained_unknown = sum(1 for s in summaries if s.maintained is None)
    open_upvotes = max((i.upvotes for i in niche.ideas if i.status in open_statuses), default=0)

    weaknesses = []
    if maintained < int(competition["fewer_than_maintained_alternatives"]):
        weaknesses.append(
            "no maintained Actor" if maintained == 0
            else f"only {maintained} maintained Actor{'s' if maintained > 1 else ''}"
        )
    if leader and leader.failure_rate is not None and leader.failure_rate > float(competition["leader_failure_rate_above"]):
        weaknesses.append(f"leader fails {leader.failure_rate:.0%} of runs")
    if leader and leader.rating is not None and leader.rating < float(competition["leader_rating_below"]):
        weaknesses.append(f"leader rated {leader.rating:.1f}")
    if leader and leader.days_since_update is not None and leader.days_since_update > max_days:
        weaknesses.append(f"leader not updated for {leader.days_since_update} days")

    users_30d = sum(a.users_30d for a in niche.actors)
    ranking = scout_cfg["ranking"]
    demand = max(float(users_30d), open_upvotes * float(ranking["idea_upvote_user_equivalent"]))
    score = math.log10(1 + demand) * (1 + float(ranking["weakness_bonus"]) * len(weaknesses))

    return Candidate(
        rank=0,
        niche_id=niche.id,
        label=niche.label,
        keywords=list(niche.keywords),
        users_7d=sum(a.users_7d for a in niche.actors),
        users_30d=users_30d,
        users_90d=sum(a.users_90d for a in niche.actors),
        actor_count=len(niche.actors),
        maintained_alternatives=maintained,
        maintained_unknown=maintained_unknown,
        leader=leader,
        alternatives=summaries[1:6],
        ideas=sorted(niche.ideas, key=lambda i: -i.upvotes)[:5],
        open_idea_upvotes=open_upvotes,
        weaknesses=weaknesses,
        demand=demand,
        score=round(score, 3),
    )


def rank(candidates: list[Candidate]) -> list[Candidate]:
    ordered = sorted(candidates, key=lambda c: (-c.score, -c.demand, c.niche_id))
    for position, candidate in enumerate(ordered, start=1):
        candidate.rank = position
    return ordered
