"""Regenerate the synthetic Apify sample responses in tests/fixtures/apify/.

    python tests/fixtures/build_fixtures.py

The development sandbox cannot reach api.apify.com or apify.com, so these
fixtures are synthetic: every Actor, username and number below is invented.
Their shape follows Apify's OpenAPI spec (StoreActor, ActorStats,
CurrentPricingInfo, Actor and the pricing-info variants). Replace them with
real captures from the Scout workflow's `scout-output` artifact (raw/) once
it has run in GitHub Actions; see tests/fixtures/README.md.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

AS_OF = datetime(2026, 10, 24, tzinfo=timezone.utc)
OUT = Path(__file__).parent / "apify"

# (username, name, title, categories, users_30d, failure_rate, rating, reviews, days_since_build, pricing)
# pricing: ("ppe", usd_per_result) | ("ppe_dataset_item", usd) | ("item", usd) | ("tiered", free_tier_usd)
#          | ("rental", usd_per_month) | ("free",)
ACTORS = [
    # Google Maps: huge, well served
    ("northwind-data", "google-maps-scraper", "Google Maps Scraper", ["LEAD_GENERATION", "TRAVEL"], 42000, 0.02, 4.6, 812, 4, ("ppe", 0.004)),
    ("lumen-labs", "google-maps-extractor", "Google Maps Extractor", ["LEAD_GENERATION"], 9100, 0.04, 4.4, 210, 12, ("ppe", 0.003)),
    ("quarry-tools", "google-maps-reviews-scraper", "Google Maps Reviews Scraper", ["LEAD_GENERATION"], 6200, 0.03, 4.5, 150, None, ("item", 0.0005)),
    ("fjord-dev", "google-maps-email-extractor", "Google Maps Email Extractor", ["LEAD_GENERATION"], 2100, 0.07, 4.1, 40, 30, ("item", 0.006)),
    ("kestrel-data", "fast-google-maps-scraper", "Fast Google Maps Scraper", ["LEAD_GENERATION"], 1300, 0.09, 4.0, 22, 60, ("ppe", 0.002)),
    ("harbor-scrapers", "google-maps-leads", "Google Maps Leads", ["LEAD_GENERATION"], 800, 0.12, 3.9, 12, 200, ("rental", 15.0)),
    # Instagram profiles: personal data
    ("tidepool", "instagram-profile-scraper", "Instagram Profile Scraper", ["SOCIAL_MEDIA"], 15000, 0.04, 4.4, 380, 6, ("ppe", 0.0023)),
    ("brightline-io", "instagram-profile-details", "Instagram Profile Details Scraper", ["SOCIAL_MEDIA"], 3200, 0.08, 4.2, 60, 20, ("item", 0.002)),
    ("cobalt-crawl", "instagram-profiles", "Instagram Profiles", ["SOCIAL_MEDIA"], 900, 0.15, 3.6, 14, 45, ("free",)),
    # LinkedIn jobs: weak competition, but login and terms
    ("meridian-io", "linkedin-jobs-scraper", "LinkedIn Jobs Scraper", ["JOBS"], 2400, 0.18, 3.6, 55, 40, ("ppe", 0.001)),
    ("parcel-bots", "linkedin-jobs-no-login", "LinkedIn Jobs Scraper - No Login", ["JOBS"], 800, 0.25, 3.2, 19, 130, ("item", 0.001)),
    ("sable-data", "linkedin-job-postings", "LinkedIn Job Postings", ["JOBS"], 300, 0.10, 4.0, 5, 15, ("free",)),
    # Amazon products: well served
    ("wren-automation", "amazon-product-scraper", "Amazon Product Scraper", ["ECOMMERCE"], 9000, 0.06, 4.2, 240, 10, ("tiered", 0.004)),
    ("orbit-tools", "amazon-product-details", "Amazon Product Details", ["ECOMMERCE"], 2500, 0.05, 4.3, 70, 25, ("item", 0.0025)),
    ("zephyr-dev", "amazon-products-api", "Amazon Products API", ["ECOMMERCE"], 1800, 0.04, 4.5, 33, 7, ("ppe", 0.0025)),
    ("alder-labs", "amazon-product-data", "Amazon Product Data Scraper", ["ECOMMERCE"], 600, 0.11, 3.9, 9, 80, ("free",)),
    # Greenhouse job boards: official public API, weak leader
    ("basalt-api", "greenhouse-jobs-scraper", "Greenhouse Jobs Scraper", ["JOBS"], 260, 0.16, 3.7, 12, 200, ("ppe_dataset_item", 0.0015)),
    ("cinder-io", "greenhouse-job-board", "Greenhouse Job Board Scraper", ["JOBS"], 45, 0.05, None, 0, 30, ("item", 0.001)),
    ("delta-fetch", "greenhouse-jobs", "Greenhouse Jobs", ["JOBS"], 12, 0.30, None, 0, 400, ("free",)),
    # Lever postings: official public API, no maintained Actor
    ("ember-data", "lever-jobs-scraper", "Lever Jobs Scraper", ["JOBS"], 120, 0.11, 4.5, 6, 100, ("ppe", 0.002)),
    ("northwind-data", "lever-job-postings", "Lever Job Postings Scraper", ["JOBS"], 30, 0.02, None, 0, 95, ("free",)),
    # SEC EDGAR: official API, stale and failing leader
    ("lumen-labs", "sec-edgar-filings-scraper", "SEC EDGAR Filings Scraper", ["BUSINESS"], 380, 0.12, 3.8, 9, 120, ("ppe", 0.002)),
    ("quarry-tools", "edgar-filings-extractor", "EDGAR Filings Extractor", ["BUSINESS"], 90, 0.03, 4.6, 3, 50, ("item", 0.003)),
    ("fjord-dev", "sec-filings-api", "SEC Filings API", ["BUSINESS"], 40, 0.01, None, 0, 10, ("free",)),
    # Hacker News: legal and stable, but well served
    ("kestrel-data", "hacker-news-scraper", "Hacker News Scraper", ["NEWS"], 220, 0.03, 4.7, 11, 14, ("free",)),
    ("harbor-scrapers", "hacker-news-posts", "Hacker News Posts", ["NEWS"], 60, 0.02, 4.8, 4, 33, ("item", 0.001)),
    ("tidepool", "hn-top-stories", "Hacker News Top Stories", ["NEWS"], 25, 0.01, None, 0, 70, ("free",)),
    # Shopify store products
    ("brightline-io", "shopify-products-scraper", "Shopify Products Scraper", ["ECOMMERCE"], 2100, 0.11, 4.3, 48, 15, ("item", 0.001)),
    ("cobalt-crawl", "shopify-store-products", "Shopify Store Products", ["ECOMMERCE"], 700, 0.06, 4.4, 20, 22, ("ppe", 0.0009)),
    ("meridian-io", "shopify-product-data", "Shopify Product Data", ["ECOMMERCE"], 300, 0.04, 4.2, 7, 40, ("free",)),
    ("parcel-bots", "shopify-catalog-scraper", "Shopify Catalog Scraper", ["ECOMMERCE"], 40, 0.0, None, 0, 300, ("free",)),
    # Trustpilot reviews: reviewer names
    ("sable-data", "trustpilot-reviews-scraper", "Trustpilot Reviews Scraper", ["MARKETING"], 1800, 0.07, 3.9, 41, 18, ("ppe", 0.0008)),
    ("wren-automation", "trustpilot-reviews", "Trustpilot Reviews", ["MARKETING"], 450, 0.09, 4.1, 9, 60, ("item", 0.0005)),
    ("orbit-tools", "trustpilot-company-reviews", "Trustpilot Company Reviews", ["MARKETING"], 200, 0.05, 4.4, 6, 12, ("free",)),
    # Zillow: failing leader, but terms, browser and proxies
    ("zephyr-dev", "zillow-scraper", "Zillow Scraper", ["REAL_ESTATE"], 4200, 0.13, 4.0, 88, 9, ("ppe", 0.002)),
    ("alder-labs", "zillow-property-scraper", "Zillow Property Scraper", ["REAL_ESTATE"], 1200, 0.10, 4.2, 24, 35, ("item", 0.002)),
    ("basalt-api", "zillow-zestimate-scraper", "Zillow Zestimate Scraper", ["REAL_ESTATE"], 300, 0.20, 3.5, 6, 150, ("free",)),
    # Product Hunt: API needs an account token
    ("cinder-io", "product-hunt-scraper", "Product Hunt Scraper", ["MARKETING"], 150, 0.22, 3.5, 8, 300, ("item", 0.003)),
    ("delta-fetch", "product-hunt-launches", "Product Hunt Launches", ["MARKETING"], 35, 0.05, None, 0, 120, ("free",)),
    # npm downloads: official API
    ("ember-data", "npm-package-downloads", "npm Package Downloads Scraper", ["DEVELOPER_TOOLS"], 120, 0.12, 4.8, 4, 100, ("ppe", 0.0005)),
    ("kestrel-data", "npm-download-stats", "npm Download Stats", ["DEVELOPER_TOOLS"], 40, 0.01, None, 0, 50, ("free",)),
    # PyPI metadata: official API, small Actor, open idea
    ("harbor-scrapers", "pypi-package-metadata", "PyPI Package Metadata Scraper", ["DEVELOPER_TOOLS"], 30, 0.01, None, 0, 95, ("free",)),
    # TED EU tenders: official API, failing leader, open idea
    ("tidepool", "ted-eu-tenders-scraper", "TED EU Tenders Scraper", ["BUSINESS"], 70, 0.19, 3.2, 5, 150, ("item", 0.004)),
    ("brightline-io", "eu-tenders", "EU Tenders", ["BUSINESS"], 20, 0.06, None, 0, 200, ("free",)),
    # Federal Register: too little demand
    ("cobalt-crawl", "federal-register-documents", "Federal Register Documents Scraper", ["NEWS"], 25, 0.0, None, 0, 30, ("free",)),
    # Booking.com: well served
    ("meridian-io", "booking-com-hotels", "Booking.com Hotels Scraper", ["TRAVEL"], 6000, 0.05, 4.5, 130, 8, ("ppe", 0.003)),
    ("parcel-bots", "booking-hotels-scraper", "Booking Hotels Scraper", ["TRAVEL"], 1500, 0.06, 4.3, 31, 20, ("item", 0.0025)),
    ("sable-data", "booking-com-reviews", "Booking.com Reviews", ["TRAVEL"], 700, 0.08, 4.0, 15, 44, ("ppe", 0.001)),
    ("wren-automation", "booking-com-prices", "Booking.com Prices", ["TRAVEL"], 300, 0.04, 4.6, 5, 30, ("free",)),
    # YouTube channels: low-rated leader, personal data and terms
    ("basalt-api", "youtube-channel-scraper", "YouTube Channel Scraper", ["VIDEOS"], 5000, 0.08, 3.8, 70, 15, ("ppe", 0.002)),
    ("cinder-io", "youtube-channel-videos", "YouTube Channel Videos", ["VIDEOS"], 1100, 0.07, 4.2, 18, 40, ("item", 0.0015)),
    # Indeed jobs: weak competition, but terms and anti-bot
    ("delta-fetch", "indeed-jobs-scraper", "Indeed Jobs Scraper", ["JOBS"], 3500, 0.15, 3.9, 60, 21, ("ppe", 0.002)),
    ("ember-data", "indeed-job-listings", "Indeed Job Listings", ["JOBS"], 900, 0.12, 4.0, 14, 55, ("item", 0.002)),
    ("northwind-data", "indeed-jobs-api", "Indeed Jobs API", ["JOBS"], 400, 0.20, 3.4, 8, 140, ("free",)),
    # Website content: well served
    ("lumen-labs", "website-content-crawler", "Website Content Crawler", ["AI", "DEVELOPER_TOOLS"], 2200, 0.01, 4.7, 90, 2, ("ppe", 0.0005)),
    ("quarry-tools", "website-content-extractor", "Website Content Extractor", ["AI"], 500, 0.03, 4.5, 12, 14, ("ppe", 0.0004)),
    ("kestrel-data", "website-content-scraper", "Website Content Scraper", ["AI"], 300, 0.05, 4.4, 6, 20, ("free",)),
    # Sitemaps: well served
    ("harbor-scrapers", "sitemap-urls-scraper", "Sitemap URLs Scraper", ["SEO_TOOLS"], 600, 0.02, 4.6, 14, 10, ("ppe", 0.0002)),
    ("tidepool", "sitemap-url-extractor", "Sitemap URL Extractor", ["SEO_TOOLS"], 300, 0.01, 4.8, 7, 30, ("free",)),
    ("brightline-io", "sitemap-urls", "Sitemap URLs", ["SEO_TOOLS"], 150, 0.03, 4.5, 3, 60, ("free",)),
    # WordPress plugins: official API, plugin authors are often people
    ("cobalt-crawl", "wordpress-plugins-scraper", "WordPress Plugins Scraper", ["DEVELOPER_TOOLS"], 85, 0.11, 4.0, 3, 120, ("item", 0.002)),
    ("meridian-io", "wordpress-plugin-stats", "WordPress Plugin Stats", ["DEVELOPER_TOOLS"], 20, 0.05, None, 0, 200, ("free",)),
    # openFDA recalls: too little demand
    ("parcel-bots", "openfda-drug-recalls", "openFDA Drug Recalls", ["OTHER"], 45, 0.0, None, 0, 30, ("free",)),
    # Steam games: unclear terms, changing layout
    ("sable-data", "steam-games-scraper", "Steam Games Scraper", ["OTHER"], 900, 0.09, 4.4, 16, 20, ("ppe", 0.001)),
    ("wren-automation", "steam-game-prices", "Steam Game Prices", ["OTHER"], 300, 0.06, 4.2, 5, 70, ("free",)),
    ("orbit-tools", "steam-store-games", "Steam Store Games", ["OTHER"], 100, 0.15, 3.9, 2, 200, ("free",)),
    # App Store reviews: well served, reviewer names
    ("zephyr-dev", "app-store-reviews-scraper", "App Store Reviews Scraper", ["MARKETING"], 1300, 0.06, 4.1, 25, 12, ("ppe", 0.0005)),
    ("alder-labs", "apple-app-store-reviews", "Apple App Store Reviews", ["MARKETING"], 400, 0.04, 4.3, 8, 30, ("item", 0.0005)),
    ("basalt-api", "app-store-review-scraper", "App Store Review Scraper", ["MARKETING"], 250, 0.05, 4.4, 4, 45, ("free",)),
    # Etsy listings: weak competition, but terms
    ("cinder-io", "etsy-listings-scraper", "Etsy Listings Scraper", ["ECOMMERCE"], 1100, 0.17, 3.4, 20, 25, ("ppe", 0.002)),
    ("delta-fetch", "etsy-shop-listings", "Etsy Shop Listings", ["ECOMMERCE"], 300, 0.10, 3.9, 6, 80, ("free",)),
    # Podcast episodes: feeds, host names
    ("ember-data", "podcast-episodes-scraper", "Podcast Episodes Scraper", ["VIDEOS"], 140, 0.04, 4.6, 7, 50, ("ppe", 0.0008)),
    ("northwind-data", "podcast-episode-feed", "Podcast Episode Feed", ["VIDEOS"], 30, 0.02, None, 0, 20, ("free",)),
    # Google Trends: weak competition, but terms and robots.txt
    ("lumen-labs", "google-trends-scraper", "Google Trends Scraper", ["SEO_TOOLS", "MARKETING"], 2500, 0.21, 3.7, 45, 30, ("ppe", 0.003)),
    ("quarry-tools", "google-trends-explorer", "Google Trends Explorer", ["SEO_TOOLS"], 600, 0.25, 3.3, 11, 90, ("item", 0.003)),
    # GitHub repositories: well served
    ("harbor-scrapers", "github-repositories-scraper", "GitHub Repositories Scraper", ["DEVELOPER_TOOLS"], 400, 0.05, 4.5, 8, 13, ("ppe", 0.001)),
    ("brightline-io", "github-repository-search", "GitHub Repository Search", ["DEVELOPER_TOOLS"], 150, 0.03, 4.4, 4, 25, ("free",)),
    ("cobalt-crawl", "github-repositories", "GitHub Repositories", ["DEVELOPER_TOOLS"], 60, 0.04, 4.2, 2, 60, ("free",)),
    # Weather forecasts: non-commercial source terms
    ("meridian-io", "weather-forecast-scraper", "Weather Forecast Scraper", ["OTHER"], 60, 0.03, 4.0, 2, 45, ("ppe", 0.0005)),
    ("parcel-bots", "weather-forecast-api", "Weather Forecast API", ["OTHER"], 15, 0.0, None, 0, 400, ("free",)),
    # Rightmove: weak competition, but terms
    ("sable-data", "rightmove-scraper", "Rightmove Scraper", ["REAL_ESTATE"], 1500, 0.14, 3.9, 30, 28, ("ppe", 0.002)),
    # Yelp reviews: well served, reviewer names
    ("orbit-tools", "yelp-reviews-scraper", "Yelp Reviews Scraper", ["MARKETING"], 1600, 0.09, 4.2, 30, 16, ("ppe", 0.001)),
    ("zephyr-dev", "yelp-business-reviews", "Yelp Business Reviews", ["MARKETING"], 500, 0.07, 4.1, 10, 30, ("item", 0.001)),
    ("alder-labs", "yelp-reviews", "Yelp Reviews", ["MARKETING"], 200, 0.05, 4.3, 3, 50, ("free",)),
]

UNDER_MAINTENANCE = {"fjord-dev/google-maps-email-extractor"}
NO_DETAIL = {"quarry-tools/google-maps-reviews-scraper"}  # detail lookup fails: build date unknown

# (slug, title, description, upvotes, status)
IDEAS = [
    ("pypi-package-metadata-scraper", "PyPI package metadata scraper",
     "Package name, versions, release dates, licence and dependencies for a list of PyPI packages.", 31, "Open to develop"),
    ("ted-eu-tenders-monitor", "TED EU tenders monitor",
     "Daily list of new EU public tenders from TED filtered by CPV code and country.", 9, "Open to develop"),
    ("federal-grant-opportunities-grants-gov", "Federal grant opportunities from Grants.gov",
     "Open US federal grant opportunities with agency, deadline, award ceiling and eligibility.", 96, "New"),
    ("court-opinions-courtlistener", "Court opinions from CourtListener",
     "New court opinions by court and date, with parties and judges.", 7, "Open to develop"),
    ("hacker-news-who-is-hiring-parser", "Hacker News Who is Hiring parser",
     "Parse the monthly Who is Hiring thread into structured job posts.", 3, "Open to develop"),
    ("wikipedia-pageviews-by-article", "Wikipedia pageviews by article",
     "Daily pageviews for a list of Wikipedia articles.", 2, "New"),
    ("shopify-app-store-reviews", "Shopify app store reviews",
     "Reviews of apps in the Shopify App Store.", 5, "In progress"),
    ("instagram-follower-export", "Instagram follower export",
     "Export the followers of an Instagram account.", 30, "Completed"),
]


def actor_id(slug: str) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    digest = hashlib.sha256(slug.encode()).digest()
    return "".join(alphabet[b % len(alphabet)] for b in digest[:17])


def iso(days_ago: float) -> str:
    return (AS_OF - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def ratio(slug: str, low: float, high: float, salt: str) -> float:
    value = int(hashlib.sha256((slug + salt).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return low + (high - low) * value


def pricing_info(pricing: tuple) -> dict:
    common = {"apifyMarginPercentage": 0.2, "createdAt": iso(400), "startedAt": iso(380)}
    kind = pricing[0]
    if kind == "free":
        return {"pricingModel": "FREE", **common}
    if kind == "item":
        return {"pricingModel": "PRICE_PER_DATASET_ITEM", "unitName": "result", "pricePerUnitUsd": pricing[1], **common}
    if kind == "tiered":
        base = pricing[1]
        tiers = {"FREE": base, "BRONZE": base * 0.9, "SILVER": base * 0.8, "GOLD": base * 0.7}
        return {
            "pricingModel": "PRICE_PER_DATASET_ITEM", "unitName": "result",
            "tieredPricing": {t: {"tieredPricePerUnitUsd": round(p, 6)} for t, p in tiers.items()}, **common,
        }
    if kind == "rental":
        return {"pricingModel": "FLAT_PRICE_PER_MONTH", "pricePerUnitUsd": pricing[1], "trialMinutes": 1440, **common}
    start = {"eventTitle": "Actor start", "eventDescription": "Charged once when the run starts.",
             "eventPriceUsd": 0.005, "isOneTimeEvent": True}
    if kind == "ppe_dataset_item":
        events = {"actor-start": start, "apify-default-dataset-item": {
            "eventTitle": "Dataset item", "eventDescription": "Charged for each item in the default dataset.",
            "eventPriceUsd": pricing[1]}}
    else:
        events = {"actor-start": start, "result": {
            "eventTitle": "Result", "eventDescription": "Charged for each result.",
            "eventPriceUsd": pricing[1], "isPrimaryEvent": True}}
    return {"pricingModel": "PAY_PER_EVENT", "pricingPerEvent": {"actorChargeEvents": events},
            "minimalMaxTotalChargeUsd": 0.5, "isPPEPlatformUsagePaidByUser": False, **common}


def build() -> None:
    items, details = [], {}
    for username, name, title, categories, users_30d, fail, rating, reviews, days, pricing in ACTORS:
        slug = f"{username}/{name}"
        total_runs = max(int(users_30d * ratio(slug, 8, 20, "runs")), 1)
        failed = round(total_runs * fail * 0.7)
        timed_out = round(total_runs * fail) - failed
        aborted = round(total_runs * 0.02)
        stats = {
            "totalBuilds": int(ratio(slug, 10, 200, "builds")),
            "totalRuns": total_runs * 14,
            "totalUsers": int(users_30d * ratio(slug, 4, 9, "total")),
            "totalUsers7Days": int(users_30d * ratio(slug, 0.3, 0.45, "7d")),
            "totalUsers30Days": users_30d,
            "totalUsers90Days": int(users_30d * ratio(slug, 2.0, 2.6, "90d")),
            "totalMetamorphs": 0,
            "lastRunStartedAt": iso(0.1),
            "actorReviewCount": reviews,
            "actorReviewRating": rating or 0,
            "bookmarkCount": int(users_30d * 0.05),
            "publicActorRunStats30Days": {
                "ABORTED": aborted, "FAILED": failed, "SUCCEEDED": total_runs - failed - timed_out - aborted,
                "TIMED-OUT": timed_out, "TOTAL": total_runs,
            },
        }
        notice = "UNDER_MAINTENANCE" if slug in UNDER_MAINTENANCE else "NONE"
        info = pricing_info(pricing)
        item = {
            "id": actor_id(slug), "title": title, "name": name, "username": username, "userFullName": None,
            "description": f"Synthetic fixture Actor: {title.lower()}.", "categories": categories, "notice": notice,
            "pictureUrl": None, "userPictureUrl": None, "url": f"https://apify.com/{slug}", "stats": stats,
            "currentPricingInfo": info, "isWhiteListedForAgenticPayments": pricing[0] != "rental",
            "actorReviewCount": reviews, "actorReviewRating": rating or 0, "bookmarkCount": stats["bookmarkCount"],
            "badge": None,
        }
        items.append(item)
        if slug in NO_DETAIL:
            continue
        build_at = iso(days) if days is not None else None
        details[item["id"]] = {"data": {
            "id": item["id"], "userId": actor_id(username), "name": name, "username": username,
            "description": item["description"], "isPublic": True, "createdAt": iso(500),
            "modifiedAt": iso((days or 0) / 2), "stats": stats, "pricingInfos": [info],
            "defaultRunOptions": {"build": "latest", "timeoutSecs": 3600, "memoryMbytes": 1024},
            "isDeprecated": False, "title": title, "categories": categories, "notice": notice,
            "taggedBuilds": {"latest": {"buildId": actor_id(slug + "build"), "buildNumber": "0.1.42", "finishedAt": build_at}},
        }}

    ideas = [
        {"id": actor_id(slug), "slug": slug, "title": title, "description": description,
         "upvotes": upvotes, "status": status, "createdAt": iso(30 + upvotes)}
        for slug, title, description, upvotes, status in IDEAS
    ]
    next_data = {"props": {"pageProps": {"ideas": ideas, "totalCount": len(ideas)}},
                 "page": "/ideas", "query": {}, "buildId": "synthetic-fixture"}
    cards = "\n".join(
        f'    <a href="/ideas/{i["slug"]}"><h3>{i["title"]}</h3><span>{i["upvotes"]}</span><span>{i["status"]}</span></a>'
        for i in ideas
    )
    html = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head><meta charset=\"utf-8\"><title>Actor ideas | Apify</title></head>\n"
        "<body>\n  <!-- Synthetic fixture: structure assumed, not captured from apify.com/ideas -->\n"
        f"  <div id=\"__next\">\n{cards}\n  </div>\n"
        f"  <script id=\"__NEXT_DATA__\" type=\"application/json\">{json.dumps(next_data)}</script>\n"
        "</body>\n</html>\n"
    )

    OUT.mkdir(exist_ok=True)
    (OUT / "store_actors.json").write_text(json.dumps(items, indent=1) + "\n", encoding="utf-8")
    (OUT / "actor_details.json").write_text(json.dumps(details, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "ideas.html").write_text(html, encoding="utf-8")
    print(f"{len(items)} Actors, {len(details)} details, {len(ideas)} ideas -> {OUT}")


if __name__ == "__main__":
    build()
