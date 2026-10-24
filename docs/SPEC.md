# Actor Factory — Specification

This is the original specification, saved verbatim. Decisions about ambiguous points are recorded in [QUESTIONS.md](QUESTIONS.md).

---

You are building the Actor Factory in this repository: AI agents that find, build, publish and maintain paid Actors on the Apify Store, with me approving the key steps. This prompt is the full spec; first save it as docs/SPEC.md.

GOAL
A portfolio of about 15 paid Actors by April 2027. Buyers find Actors through the Apify Store, Google and AI agents (Apify's MCP server). No outreach of any kind.

AGENTS (Python 3.12, scheduled with GitHub Actions)
1. Scout, weekly: read the public Apify Store endpoint (https://api.apify.com/v2/store, no key needed) and the Apify Ideas page (https://apify.com/ideas). For each candidate niche record: users over 7/30/90 days, 30-day run failure rate, rating, days since last update, price. Open one GitHub issue per week listing 20 candidates with these numbers.
2. Validator, after each Scout run: score every candidate with claude-sonnet-5-5 on five checks and post a one-page brief as an issue comment.
   - Demand: at least 50 users in 30 days across similar Actors, or an open idea with upvotes
   - Competition: fewer than 3 maintained alternatives, or the leader fails over 10% of runs or is rated below 4
   - Legality: public pages, no login, no personal data, and the site's terms and robots.txt allow it
   - Cost: platform cost under 30% of the price per 1,000 results
   - Stability: an official API or feed, or a site that rarely changes its layout
   Never pass Legality if the data needs a login or contains personal data. Keep the thresholds in config.yaml.
3. Builder: when I add the label "go" to a candidate issue, the Claude Code GitHub Action opens a pull request with the Actor in actors/<name>/ (from the official Apify Python template): code, tests, input schema, a Store README and pay-per-event pricing (per result). Never merge; I merge.
4. Publisher: on merge to main, deploy with the Apify CLI (apify push) and prepare the Store listing text. I click Publish once per new Actor in Apify Console.
5. Watcher, daily: pull runs, failures, reviews and revenue for my Actors through the Apify API (APIFY_TOKEN). Open an issue labelled "broken" when the 24-hour failure rate passes 10%. Pass a summary to the next Scout run.
6. Fixer: on a "broken" issue, the Claude Code GitHub Action opens a fix pull request that includes a test reproducing the failure.
Digest, Mondays: email me one page with revenue, users, failures and the decisions waiting for me.

LAYOUT
factory/scout, factory/validator, factory/watcher, factory/digest
actors/<name>/
.github/workflows/ (scout.yml weekly, watcher.yml daily, digest.yml weekly, claude.yml for the Claude Code GitHub Action)
config.yaml, docs/SPEC.md, CLAUDE.md, CHANGELOG.md, .env.example

RULES
- Work one phase at a time. At the end of each phase run all tests, update CHANGELOG.md, list what you could not do, and stop for my review.
- Secrets only in GitHub Actions secrets: APIFY_TOKEN, ANTHROPIC_API_KEY, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, DIGEST_TO. Never commit keys.
- Every Actor: polite rate limits, retries with back-off, respects robots.txt, outputs no personal data.
- If your environment blocks a network call (for example to api.apify.com), write the code against saved sample responses in tests/fixtures/ and note which steps must run in GitHub Actions.
- When something is ambiguous, write the question in docs/QUESTIONS.md, choose the conservative option and continue.

PHASES
1. Now: CLAUDE.md, docs/SPEC.md, the scaffold, Scout and Validator with tests, scout.yml. Done when a dry run builds the weekly issue body with 20 scored candidates from sample data.
2. Builder and Publisher, and the first 3 Actors.
3. Watcher and Fixer.
4. Digest, and scale to 8 Actors.

Start Phase 1 now, work on a branch named phase-1, and push it when the phase is done.
