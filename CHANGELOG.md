# Changelog

## Phase 1 fixes after the first live run (2026-10-24, branch `phase-1-live-fixes`)

The first run against live data (Scout and the Validator, both as dry runs, from the owner's machine) worked end to end: 9,688 Store Actors from 19 queries, 245 Actor detail lookups, 148 ideas, and 20 Claude assessments in about 2.5 minutes for roughly $0.15. It found two problems, fixed here:

- **Ideas:** the Ideas page loads its list in the browser, so none were parsed. Scout now reads the page's own export (`/api/ideas/download?format=json&status=toDevelop`) and takes each idea's upvotes from its page (QUESTIONS Q4). New config: `apify.ideas_export_url`, `scout.ideas.max_pages`. Only `open_to_develop` counts as open.
- **Niche grouping:** real titles carry sales text after a separator ("Tweet Scraper V2 - X Scraper / Twitter Scraper…"). Keywords now come from the part before the first separator, pure numbers are ignored and `com` is a stopword. The same Store data grouped into 3,955 niches instead of 5,111.
- `owner.apify_username` is set to `guayox` (Q7).
- Fixtures: a synthetic Ideas export and idea pages replace the guessed `ideas.html`, plus small real samples of the export and an idea page. A Booking.com sample assessment was added because the new grouping brings that niche into the sample top 20.
- The `APIFY_TOKEN` and `ANTHROPIC_API_KEY` GitHub Actions secrets are set.
- **Shortlist (QUESTIONS Q13):** on live data no candidate passed, because the top 20 by demand were social-media and lead-list scrapers and generic tools. Scout now leaves out niches that can never pass (`scout.exclude`: title words and Store categories), shortlists 40 (`scout.candidates_to_validate`), and the Validator assesses all 40 and rewrites the issue with the best 20 after validation, passing candidates first. `scout.details.niche_pool` rises from 40 to 50. On the 2026-10-24 data, 1,805 of 3,955 niches were left out and the shortlist became G2 reviews, Flashscore and Sofascore, Yandex search, SEO tools, Greenhouse jobs, sitemaps and retail products, among others.

## Phase 1: Scout and Validator (2026-10-24, branch `phase-1`)

### Added

- **Project scaffold:** `docs/SPEC.md` (the spec, verbatim), `CLAUDE.md`, `docs/QUESTIONS.md`, `README.md`, `.env.example`, `.gitignore`, `pyproject.toml` (Python 3.12) and `config.yaml`, which holds every threshold. Placeholder packages for `factory/watcher` and `factory/digest`, and `actors/README.md`.
- **Shared code (`factory/common`):**
  - `PoliteClient`: at most one request per second to each host, and up to four retries with exponential back-off and jitter on 408, 425, 429, 5xx and network errors, honouring `Retry-After`.
  - A config loader.
  - A small GitHub client whose writes are idempotent: the weekly issue is found by title and label, and comments by a hidden marker.
- **Scout (`python -m factory.scout`):**
  - Reads the public Store endpoint with one query per category, plus one unfiltered query, because each query is capped at 1,000 records.
  - Looks up Actor details (latest build date, deprecation, pricing) for the best 40 niches.
  - Parses the Ideas page from its embedded JSON.
  - Groups Actors into niches by title keywords and attaches matching ideas. Open ideas with no matching Actor become niches of their own.
  - Ranks niches by demand and competition gaps, then opens one issue a week listing 20 candidates. For each it shows users over 7/30/90 days, the leader's 30-day failure rate, rating, days since last update and price, how many Actors are maintained, and open-idea upvotes.
  - Skips niches where you already have an Actor (once `owner.apify_username` is set).
  - Includes a Watcher summary when given one (`--watcher-summary`).
- **Validator (`python -m factory.validator`):**
  - One `claude-sonnet-5-5` call per candidate, with structured JSON output, a cached system prompt and a server-side refusal fallback. The model reports facts.
  - Code decides Demand, Competition, Legality, Cost and Stability using the thresholds in `config.yaml`.
  - Code enforces the hard rules: data behind a login, or personal data, never passes. "Unknown" never counts as a pass.
  - Checks robots.txt live against the URLs the Actor would request, using RFC 9309 matching. Python's `robotparser` ignores the `*` and `$` wildcards, so the matcher is written from scratch.
  - Posts a one-page brief as a single comment on the weekly issue (re-runs edit it), and adds a Checks column to the issue's table.
- **Dry run (`python -m factory.dry_run`):** runs Scout and the Validator offline on sample data. It writes the issue body with 20 scored candidates, the brief, and a combined preview to `out/dry-run/`. A snapshot is in `docs/examples/dry-run-issue.md`.
- **Workflows:**
  - `scout.yml`: weekly on Sundays at 05:17 UTC, with a manual dry-run option. It runs the tests, then Scout, then the Validator, and uploads the outputs and raw API responses as the `scout-output` artifact.
  - `tests.yml`: runs the tests and the dry run on pull requests and on pushes to `main`.
- **Tests:** 152 pytest tests, all offline. They cover the HTTP retries, the GitHub client, Store, pricing and Ideas parsing, clustering, ranking, the issue body, robots.txt matching, each of the five checks and their hard rules, the Claude request shape and error handling, the brief, the CLIs, the dry run, and repository guards (thresholds match the spec, only the listed secrets are used, no keys are committed).
- **Fixtures:** Apify's documented OpenAPI examples, plus synthetic Store, Actor-detail and Ideas data in the same shapes, hand-written sample assessments and synthetic robots.txt files. Their provenance is in `tests/fixtures/README.md`.

### Could not do in Phase 1

- **No live Apify data.** The development sandbox blocks `api.apify.com` and `apify.com`. Response parsing follows Apify's OpenAPI spec (read from GitHub) and is tested only on documented examples and synthetic data. The first real run will be in GitHub Actions.
- **The Ideas page structure is unverified.** The parser and its fixture are a best guess (QUESTIONS Q4). If nothing is parsed, the issue shows a warning.
- **No real Claude call.** There is no `ANTHROPIC_API_KEY` here, so the request is tested against a fake client and the sample assessments are hand-written, not model output.
- **No real GitHub writes.** Opening the issue and posting the comment are tested against a fake GitHub API. `scout.yml` has not run yet.
- **These steps must run in GitHub Actions:** the Store, Actor-detail and Ideas fetches, the robots.txt fetches, the Claude calls, and the issue and comment writes.
- **Needs your setup:**
  - Add the `APIFY_TOKEN` and `ANTHROPIC_API_KEY` secrets.
  - Merge to `main` so the weekly schedule starts. GitHub runs scheduled workflows only from the default branch.
  - Answer QUESTIONS Q1, Q5 and Q7.
- **Left for later phases:** the Builder, Publisher, Watcher, Fixer and Digest, and `claude.yml`, `watcher.yml` and `digest.yml`. Scout does not yet remember which candidates were proposed in earlier weeks.
