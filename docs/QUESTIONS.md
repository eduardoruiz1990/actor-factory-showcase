# Open questions

When the spec was ambiguous, the question is recorded here with the option chosen. The chosen option is always the conservative one, and each can be changed. Most are a single setting in `config.yaml`.

Status: **open** means it needs your answer; **assumed** means a choice was made and the work continued.

---

### Q1. How does the `go` label pick which candidate to build? (open, needed for Phase 2)

The spec has Scout open **one issue per week listing 20 candidates**, and the Builder start "when I add the label `go` to a candidate issue". A label on the weekly issue cannot say which of the 20 you mean.

- Phase 1: one weekly issue, exactly as specified. Every candidate has a stable niche id (for example `greenhouse-job`) in the table, the brief and the hidden JSON.
- Proposal for Phase 2: add `go`, then comment `/build <niche-id>`. If there is no such comment, the Builder builds nothing and asks which candidate you mean. It never builds a candidate that failed a check.
- Alternative: Scout also opens one small issue per passing candidate, and you label that issue `go`.

### Q2. One brief for all 20 candidates, or one per candidate? (assumed)

The Validator posts **one comment** with a one-page brief covering all 20 candidates: a pass/fail table, details for the top three passing candidates, and one line for each candidate that failed. It also adds a **Checks** column to the issue's own table, so the issue body shows 20 scored candidates. Re-runs edit the same comment instead of adding a new one.

### Q3. What counts as a "maintained" alternative? (assumed)

An Actor whose latest build finished within **90 days** (`scout.maintained_max_days_since_update`) and that is not marked `UNDER_MAINTENANCE`. The Store list has no update date, so Scout looks up Actor details (`GET /v2/acts/{id}`) for the 10 most-used Actors in each of the 40 best niches. **An Actor whose build date is unknown counts as maintained.** That can only make competition look stronger. The issue marks such counts with `+`.

### Q4. The Ideas page format is unverified (assumed; check after the first live run)

`apify.com` is blocked in the development sandbox, so the real Ideas page could not be inspected. The parser reads the JSON the page embeds (a Next.js `__NEXT_DATA__` script or any other `application/json` script) and takes every object with a title and an upvote count. The fixture `tests/fixtures/apify/ideas.html` is synthetic.

- Only ideas whose status is one of `open`, `open_to_develop` or `new` (`scout.ideas.open_statuses`) count as open. An idea with any other status, or none, does not count towards Demand.
- If the page is fetched but no ideas are parsed, the weekly issue shows a warning instead of failing silently. If that happens, download the `scout-output` artifact, save `raw/ideas.html` as the fixture, and adjust `factory/scout/ideas.py`.

### Q5. Inputs to the Cost check (open)

"Platform cost under 30% of the price per 1,000 results" needs a platform cost and a price:

- Compute is priced at **$0.40 per compute unit**, the most expensive tier, and residential proxy traffic at **$8 per GB** (`apify.compute_unit_usd`, `apify.residential_proxy_usd_per_gb`). Please confirm the values for your Apify plan.
- The model estimates compute units per 1,000 results. Code raises any estimate below a floor for the approach: 0.02 CU for an official API, 0.10 for plain HTTP and 1.0 for a browser.
- The **planned price** is **80% of the niche leader's price** per 1,000 results, on the assumption that a new Actor must undercut the leader. When the leader is free or has no per-result price, the planned price is a **$2.00 default**.
- Apify's 20% commission is not counted as platform cost, because the spec says "platform cost". If the 30% should include it, the limit becomes stricter.

### Q6. Personal data the Actor could leave out (assumed)

The spec says Legality never passes when the data contains personal data. The model separates `core` personal data (profiles, reviews with their authors) from `removable` personal data: the source contains some, but the useful output works without it, such as author fields in PyPI metadata. **Both fail** by default (`validator.legality.allow_removable_personal_data: false`). Set the flag to `true` if you accept Actors that strip those fields. `core` personal data and data behind a login fail either way, because code enforces those rules.

### Q7. Your Apify username (open)

`owner.apify_username` in `config.yaml` is empty. Once it is set, Scout skips niches where you already have an Actor, and it can later tell your Actors apart from competitors.

### Q8. How the Scout numbers are defined (assumed)

- **Users over 7/30/90 days** are summed across all Actors in a niche, so one person using two Actors counts twice. This matches "50 users in 30 days across similar Actors".
- **30-day failure rate**, **rating**, **days since last update** and **price** are the niche leader's, meaning its most-used Actor. The issue also lists the other Actors with their own numbers.
- **Failure rate** = (FAILED + TIMED-OUT) / all runs in Apify's `publicActorRunStats30Days`, which excludes the developer's own runs. ABORTED runs are usually stopped by the user, so they are not counted (`scout.failure_statuses`).
- **Unrated** Actors, which have no reviews, do not count as "rated below 4".
- A **niche** is a group of Actors whose title keywords overlap (a Jaccard similarity of at least 0.5 with the leader's keywords). Open ideas that match no Actor become niches of their own.

### Q9. Reading a site's terms (assumed)

The Validator does not download and read each site's terms of service. The model reports what it knows (`yes`, `no` or `unclear`) and names the relevant term. **"Unclear" never passes.** robots.txt, by contrast, is fetched live and checked against the URLs the Actor would request, with RFC 9309 wildcard matching. A robots.txt that cannot be read (other than a 404) also leaves Legality unknown. Should a later phase fetch and check the terms pages too?

### Q10. Model settings for the Validator (assumed)

- `claude-sonnet-5-5` at `effort: medium` with structured JSON output. One request per candidate, so 20 a week. The shared system prompt is cached.
- Server-side refusal fallback is on (`fallbacks: "default"`, a beta). If the model declines a request on safety grounds, the API retries it on Anthropic's recommended fallback model, and the brief names the model that answered. Turn it off with `validator.server_side_fallback: false`.
- If a single assessment fails (a refusal or an API error), that candidate's Legality, Cost and Stability checks show as unknown and the run continues. If every assessment fails, the workflow step fails so the run shows red.

### Q11. Schedule (assumed)

Scout and the Validator run **Sundays at 05:17 UTC**, so Monday's digest (Phase 4) can include the new candidates. Tell me your time zone if you want a different time.

### Q12. A tests workflow that is not in the spec (assumed)

`.github/workflows/tests.yml` runs the test suite and the offline dry run on every pull request and on pushes to `main`. The spec does not list it, but it means the Builder's and Fixer's pull requests are tested before you merge them. It needs no secrets. Delete it if you don't want it.
