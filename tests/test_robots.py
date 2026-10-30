import pytest

from factory.validator.robots import RobotsChecker, RobotsTxt

ROBOTS = """\
User-agent: Googlebot
Disallow:

User-agent: *
Disallow: /private
Allow: /private/public
Disallow: /*.json$
Disallow: /homes/*_rb/
Disallow: /search?   # a comment
"""


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://x.com/", True),
        ("https://x.com/private/file", False),
        ("https://x.com/private/public/page", True),  # longer Allow wins
        ("https://x.com/data/items.json", False),  # * and $ wildcards
        ("https://x.com/data/items.json?page=2", True),  # $ anchors the end
        ("https://x.com/homes/for_sale/Austin-TX_rb/", False),
        ("https://x.com/search?q=1", False),
        ("https://x.com/searching", True),
    ],
)
def test_rfc9309_matching(url, allowed):
    assert RobotsTxt(ROBOTS).allows(url, "*") is allowed


def test_named_group_overrides_the_star_group():
    robots = RobotsTxt(ROBOTS)
    assert robots.allows("https://x.com/private/file", "Googlebot") is True
    assert robots.allows("https://x.com/private/file", "OtherBot/1.0") is False


def test_allow_wins_a_tie():
    assert RobotsTxt("User-agent: *\nDisallow: /page\nAllow: /page\n").allows("https://x.com/page") is True


def test_empty_disallow_and_no_groups_allow_everything():
    assert RobotsTxt("User-agent: *\nDisallow:\n").allows("https://x.com/anything") is True
    assert RobotsTxt("").allows("https://x.com/anything") is True


def test_disallow_all():
    assert RobotsTxt("User-agent: *\nDisallow: /\n").allows("https://x.com/a") is False


def checker(responses):
    calls = []

    def fetch(origin):
        calls.append(origin)
        return responses[origin]

    return RobotsChecker(fetch), calls


def test_404_means_no_restrictions():
    robots, _ = checker({"https://api.x.com": (404, "")})
    result = robots.check(["https://api.x.com/v1/jobs"])
    assert result.allowed is True and "no robots.txt" in result.detail


@pytest.mark.parametrize("status", [401, 403])
def test_other_4xx_means_no_robots_txt(status):
    # RFC 9309 2.3.1.3 (Q19): Ashby's API answers /robots.txt with 401.
    robots, _ = checker({"https://api.x.com": (status, "")})
    result = robots.check(["https://api.x.com/v1/jobs"])
    assert result.allowed is True and f"has no robots.txt (HTTP {status})" in result.detail


@pytest.mark.parametrize("status", [None, 429, 500, 503])
def test_unreadable_robots_is_unknown(status):
    robots, _ = checker({"https://x.com": (status, "")})
    assert robots.check(["https://x.com/a"]).allowed is None


def test_disallowed_url_fails_and_robots_is_cached():
    robots, calls = checker({"https://x.com": (200, "User-agent: *\nDisallow: /b\n")})
    assert robots.check(["https://x.com/a"]).allowed is True
    result = robots.check(["https://x.com/a", "https://x.com/b/c"])
    assert result.allowed is False and "/b/c" in result.detail
    assert calls == ["https://x.com"]


@pytest.mark.parametrize(
    "url", ["http://localhost/a", "http://127.0.0.1/a", "http://10.0.0.5/a", "file:///etc/passwd",
            "https://metadata.internal/a", "http://[::1]/a"],
)
def test_never_fetches_internal_hosts(url):
    robots, calls = checker({})
    assert robots.check([url]).allowed is None
    assert calls == []


def test_falls_back_to_the_domain_root():
    robots, calls = checker({"https://x.com": (200, "User-agent: *\nAllow: /\n")})
    assert robots.check([], "x.com").allowed is True
    assert robots.check([], "").allowed is None
