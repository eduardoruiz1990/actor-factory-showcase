from datetime import datetime, timedelta, timezone

from factory.scout.models import ActorRecord, Idea
from factory.scout.niches import attach_ideas, build_candidate, cluster_actors, is_maintained, jaccard, keywords

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
STOP = {"scraper", "api", "the", "data", "from"}


def actor(slug, title, users=100, days=10, **kwargs):
    username, name = slug.split("/")
    build = (NOW - timedelta(days=days)).isoformat() if days is not None else None
    return ActorRecord(id=slug, username=username, name=name, title=title, url=f"https://apify.com/{slug}",
                       users_30d=users, last_build_at=build, **kwargs)


def test_keywords_drop_stopwords_and_singularise():
    assert keywords("Google Maps Reviews Scraper", STOP) == ("google", "map", "review")
    assert keywords("Indeed Jobs API", STOP) == ("indeed", "job")
    assert keywords("Grant opportunities", STOP) == ("grant", "opportunity")
    assert keywords("Hacker News", STOP) == ("hacker", "news")
    assert keywords("The Scraper", STOP) == ()


def test_jaccard():
    assert jaccard(("google", "map"), ("google", "map", "review")) == 2 / 3
    assert jaccard(("amazon", "product"), ("amazon", "review")) == 1 / 3
    assert jaccard((), ("a",)) == 0.0


def test_similar_titles_share_a_niche_and_the_biggest_leads():
    actors = [
        actor("a/maps-reviews", "Google Maps Reviews Scraper", users=50),
        actor("b/maps", "Google Maps Scraper", users=900),
        actor("c/search", "Google Search Scraper", users=400),
    ]
    niches = cluster_actors(actors, STOP, 0.5)
    by_id = {n.id: n for n in niches}
    assert set(by_id) == {"google-map", "google-search"}
    assert [a.slug for a in by_id["google-map"].actors] == ["b/maps", "a/maps-reviews"]


def test_ideas_attach_to_matching_niches_and_open_ones_become_niches():
    niches = cluster_actors([actor("a/ted", "TED EU Tenders Scraper")], STOP, 0.5)
    ideas = [
        Idea("TED EU tenders monitor", "u1", 9, "open_to_develop"),
        Idea("Grants from Grants.gov", "u2", 20, "new"),
        Idea("Instagram follower export", "u3", 30, "completed"),
    ]
    result = attach_ideas(niches, ideas, STOP, 0.5, {"open_to_develop", "new"})
    ids = [n.id for n in result]
    assert ids == ["ted-eu-tender", "grant-gov"]
    assert result[0].ideas[0].title == "TED EU tenders monitor"


def test_maintained_rules():
    assert is_maintained(actor("a/x", "X", days=30), NOW, 90) is True
    assert is_maintained(actor("a/x", "X", days=120), NOW, 90) is False
    assert is_maintained(actor("a/x", "X", days=None), NOW, 90) is None
    assert is_maintained(actor("a/x", "X", days=1, notice="UNDER_MAINTENANCE"), NOW, 90) is False
    assert is_maintained(actor("a/x", "X", days=1, is_deprecated=True), NOW, 90) is False


def test_candidate_counts_unknown_build_dates_as_maintained(config):
    niches = cluster_actors(
        [actor("a/x", "Widget Scraper", 300, days=10), actor("b/x", "Widget Scraper Pro", 200, days=None),
         actor("c/x", "Widgets", 100, days=400)],
        STOP | {"pro"}, 0.5,
    )
    candidate = build_candidate(niches[0], NOW, config)
    assert candidate.maintained_alternatives == 2
    assert candidate.maintained_unknown == 1
    assert candidate.users_30d == 600
    assert candidate.alternatives[0].maintained is None


def test_weaknesses_raise_the_score(config):
    strong = cluster_actors([actor("a/x", "Alpha Scraper", 500, runs_30d_total=100, runs_30d_failed=1, rating=4.8)], STOP, 0.5)[0]
    weak = cluster_actors([actor("b/x", "Beta Scraper", 500, days=200, runs_30d_total=100, runs_30d_failed=30, rating=3.0)], STOP, 0.5)[0]
    strong_c, weak_c = build_candidate(strong, NOW, config), build_candidate(weak, NOW, config)
    assert strong_c.weaknesses == ["only 1 maintained Actor"]
    assert weak_c.weaknesses == [
        "no maintained Actor", "leader fails 30% of runs", "leader rated 3.0", "leader not updated for 200 days",
    ]
    assert weak_c.score > strong_c.score


def test_idea_only_demand_uses_upvote_weight(config):
    [niche] = attach_ideas([], [Idea("Grants from Grants.gov", "u", 12, "new")], STOP, 0.5, {"new"})
    candidate = build_candidate(niche, NOW, config)
    assert candidate.leader is None
    assert candidate.open_idea_upvotes == 12
    assert candidate.demand == 12 * config["scout"]["ranking"]["idea_upvote_user_equivalent"]
