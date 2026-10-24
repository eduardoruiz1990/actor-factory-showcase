"""Data records Scout produces and the Validator consumes (via out/scout.json)."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ActorRecord:
    """One public Store Actor, flattened from the Store API item."""

    id: str
    username: str
    name: str
    title: str
    url: str
    description: str = ""
    categories: list[str] = field(default_factory=list)
    users_7d: int = 0
    users_30d: int = 0
    users_90d: int = 0
    runs_30d_total: int = 0
    runs_30d_failed: int = 0
    rating: float | None = None
    review_count: int = 0
    notice: str | None = None
    pricing_model: str = "UNKNOWN"
    price_per_1000_usd: float | None = None
    price_label: str = "unknown"
    last_build_at: str | None = None  # ISO 8601, from the Actor detail lookup
    is_deprecated: bool = False

    @property
    def slug(self) -> str:
        return f"{self.username}/{self.name}"

    @property
    def failure_rate(self) -> float | None:
        if self.runs_30d_total <= 0:
            return None
        return self.runs_30d_failed / self.runs_30d_total


@dataclass
class Idea:
    """One entry from the Apify Ideas page."""

    title: str
    url: str
    upvotes: int = 0
    status: str = ""  # normalised: lower case, words joined by "_"
    description: str = ""


@dataclass
class ActorSummary:
    """The numbers the issue shows for one Actor in a niche."""

    slug: str
    title: str
    url: str
    users_30d: int
    failure_rate: float | None
    runs_30d_total: int
    rating: float | None
    review_count: int
    days_since_update: int | None
    price_per_1000_usd: float | None
    price_label: str
    pricing_model: str
    maintained: bool | None  # None: build date unknown


@dataclass
class Candidate:
    """A ranked candidate niche, as listed in the weekly issue."""

    rank: int
    niche_id: str
    label: str
    keywords: list[str]
    users_7d: int
    users_30d: int
    users_90d: int
    actor_count: int
    maintained_alternatives: int
    maintained_unknown: int  # alternatives counted as maintained because their build date is unknown
    leader: ActorSummary | None
    alternatives: list[ActorSummary]
    ideas: list[Idea]
    open_idea_upvotes: int
    weaknesses: list[str]
    demand: float
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Candidate":
        values = dict(data)
        values["leader"] = ActorSummary(**data["leader"]) if data.get("leader") else None
        values["alternatives"] = [ActorSummary(**a) for a in data.get("alternatives", [])]
        values["ideas"] = [Idea(**i) for i in data.get("ideas", [])]
        return cls(**values)
