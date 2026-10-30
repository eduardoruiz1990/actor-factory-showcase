# Open questions

When the spec was ambiguous, the question is recorded here with the option chosen. The chosen option is always the conservative one, and each can be changed. Most are a single setting in `config.yaml`.

Status: **open** means it needs your answer; **assumed** means a choice was made and the work continued.

---

### Q1. How the `go` label picks which candidate to build (resolved 2026-10-25)

You add the `go` label to the weekly Scout issue, then comment `/build <niche-id>`, for example `/build greenhouse-job`.

- **A `go` label alone:** the Builder replies with the ids of the candidates that passed all five checks.
- **A `/build` command:** before Claude starts, code checks four things. The issue has both the `scout` and `go` labels, the niche passed all five checks in the Validator's data, the proposed Actor name is valid, and `actors/<name>/` does not exist yet. If any check fails, the Builder says why on the issue and builds nothing.
- **Who can trigger it:** only the repository owner, for both the label and the command.

### Q2. One brief for all 20 candidates, or one per candidate? (assumed)

The Validator posts **one comment** with a one-page brief covering all 20 candidates: a pass/fail table, details for the top three passing candidates, and one line for each candidate that failed. It also adds a **Checks** column to the issue's own table, so the issue body shows 20 scored candidates. Re-runs edit the same comment instead of adding a new one.

### Q3. What counts as a "maintained" alternative? (assumed)

An Actor whose latest build finished within **90 days** (`scout.maintained_max_days_since_update`) and that is not marked `UNDER_MAINTENANCE`. The Store list has no update date, so Scout looks up Actor details (`GET /v2/acts/{id}`) for the 10 most-used Actors in each of the 40 best niches. **An Actor whose build date is unknown counts as maintained.** That can only make competition look stronger. The issue marks such counts with `+`.

### Q4. Where Ideas come from (resolved 2026-10-24 by the first live run)

The Ideas page loads its list in the browser, so its HTML holds no ideas, and the first live run parsed none. Scout now reads:

- **The list** from the export behind the page's own "Export ideas" button: `https://apify.com/api/ideas/download?format=json&status=toDevelop`. It returns every idea still open to develop (148 on 2026-10-24), with title, description, categories and URL, but no votes.
- **Upvotes** from each idea's page, where they sit in an element marked `data-test="upvotes"`. That is one request per idea at one per second, about 2.5 minutes a week, capped by `scout.ideas.max_pages`.

`apify.com/robots.txt` allows both. An idea whose page shows no count keeps 0 upvotes, so it cannot pass Demand on its own, and the issue reports how many were unknown. Only URLs under `https://apify.com/ideas/` are fetched.

### Q5. Inputs to the Cost check (open)

"Platform cost under 30% of the price per 1,000 results" needs a platform cost and a price:

- Compute is priced at **$0.40 per compute unit**, the most expensive tier, and residential proxy traffic at **$8 per GB** (`apify.compute_unit_usd`, `apify.residential_proxy_usd_per_gb`). Please confirm the values for your Apify plan.
- The model estimates compute units per 1,000 results. Code raises any estimate below a floor for the approach: 0.02 CU for an official API, 0.10 for plain HTTP and 1.0 for a browser.
- The **planned price** is **80% of the niche leader's price** per 1,000 results, on the assumption that a new Actor must undercut the leader. When the leader is free or has no per-result price, the planned price is a **$2.00 default**.
- Apify's 20% commission is not counted as platform cost, because the spec says "platform cost". If the 30% should include it, the limit becomes stricter.

### Q6. Personal data the Actor could leave out (resolved 2026-10-25: allowed)

The spec says Legality never passes when the data contains personal data. The model separates `core` personal data (profiles, reviews with their authors) from `removable` personal data: the source contains some, but the useful output works without it, such as author fields in PyPI metadata or a recruiter's name inside a job post.

- **Your decision (2026-10-25):** removable personal data no longer blocks Legality (`validator.legality.allow_removable_personal_data: true`), and it can reach PASS. Until then both kinds failed, which ruled out Greenhouse in week 43.
- **Still enforced:** the Actor must output none of it. The build brief tells the Builder to leave those fields out and add their names to `EXTRA_FORBIDDEN_KEYS`, and every item passes through the privacy guard.
- **Unchanged:** `core` personal data and data behind a login fail either way, because code enforces those rules.
- **To go back:** set the flag to `false`.

### Q7. Your Apify username (resolved 2026-10-24)

`owner.apify_username` is `guayox`. Scout skips niches where you already have an Actor.

### Q8. How the Scout numbers are defined (assumed)

- **Users over 7/30/90 days** are summed across all Actors in a niche, so one person using two Actors counts twice. This matches "50 users in 30 days across similar Actors".
- **30-day failure rate**, **rating**, **days since last update** and **price** are the niche leader's, meaning its most-used Actor. The issue also lists the other Actors with their own numbers.
- **Failure rate** = (FAILED + TIMED-OUT) / all runs in Apify's `publicActorRunStats30Days`, which excludes the developer's own runs. ABORTED runs are usually stopped by the user, so they are not counted (`scout.failure_statuses`).
- **Unrated** Actors, which have no reviews, do not count as "rated below 4".
- A **niche** is a group of Actors whose title keywords overlap (a Jaccard similarity of at least 0.5 with the leader's keywords). Open ideas that match no Actor become niches of their own.

### Q9. Reading a site's terms (resolved 2026-10-25: the Validator researches them)

The first live runs showed the model answering "terms unclear" for most candidates, because it could not read the terms. Now:

- **Research:** each assessment can use Claude's web search and web fetch tools: up to 3 searches and 5 page fetches (`validator.research`). The prompt tells it to find the target's own API, developer or service terms, or the data's licence, and to read the part about automated access and reuse before answering.
- **Evidence:** it must return the page's URL (`terms_source_url`) and the deciding sentence word for word (`terms_quote`). Code accepts "terms allow it" only with both (`validator.legality.require_terms_source`). Without them the terms count as unclear, and unclear never passes.
- **In the brief:** each passing candidate shows the quote and a link to its source, so you can check it before adding `go`.
- **robots.txt** is still fetched live and checked against the URLs the Actor would request, with RFC 9309 matching. A robots.txt that cannot be read (other than a 404) leaves Legality unknown.

Pages the model reads can be written by anyone. They are treated as data: the model reports what they say, and code makes the decision.

### Q10. Model settings for the Validator (assumed)

- `claude-sonnet-5-5` at `effort: medium` with structured JSON output and web research (Q9). One request per candidate, 40 a week, 4 at a time (`validator.concurrency`). The shared system prompt is cached. With research, a run costs more than the first live run's $0.15. A researched candidate used about 30,000–100,000 cached input tokens, 1,000–2,500 output tokens and up to 3 searches, so expect roughly $1–2 a week. Check it in the Claude Console after the first runs.
- Server-side refusal fallback is on (`fallbacks: "default"`, a beta). If the model declines a request on safety grounds, the API retries it on Anthropic's recommended fallback model, and the brief names the model that answered. Turn it off with `validator.server_side_fallback: false`.
- If a single assessment fails (a refusal or an API error), that candidate's Legality, Cost and Stability checks show as unknown and the run continues. If every assessment fails, the workflow step fails so the run shows red.

### Q11. Schedule (assumed)

Scout and the Validator run **Sundays at 05:17 UTC**, so Monday's digest (Phase 4) can include the new candidates. Tell me your time zone if you want a different time.

### Q12. A tests workflow that is not in the spec (assumed)

`.github/workflows/tests.yml` runs the test suite and the offline dry run on every pull request and on pushes to `main`. The spec does not list it, but it means the Builder's and Fixer's pull requests are tested before you merge them. It needs no secrets. Delete it if you don't want it.

### Q13. Scout's top 20 on live data were niches that can never pass (assumed: option 3, built 2026-10-25)

On 2026-10-24 none of the 20 live candidates passed. The niches with the most demand were social media (Instagram, TikTok, X, Facebook), lead lists (Apollo, emails) and generic scraping tools (Playwright, Cheerio, RAG Web Browser). The first two always fail Legality; the last are platform utilities, not niches.

What Scout and the Validator do now:

1. **Scout leaves out niches that can never pass** (`scout.exclude` in `config.yaml`): any niche whose title keywords include a listed word (social networks, people and lead data, generic tools and templates), or whose leading Actor is in the `SOCIAL_MEDIA` or `LEAD_GENERATION` category. On the 2026-10-24 data that left out 1,805 of 3,955 niches. Edit the lists freely. The category rule could hide a company-data niche filed under lead generation; remove `LEAD_GENERATION` if you see that happen.
2. **The Validator assesses the top 40** (`scout.candidates_to_validate`), not 20, and the issue lists the 20 best after validation: candidates passing all five checks first, then by checks passed, then by Scout's score. The issue body is rewritten with that order once the Validator finishes, and the brief says how many were assessed. That is 40 Claude calls a week, roughly $0.30 by the token counts of the first live run.

### Q14. Where pay-per-event pricing is set (assumed)

Pricing is entered once per Actor in Apify Console (**Publishing → Monetization**), not by the Publisher through the API. Apify treats raising a price or adding a paid event as a significant change: users get 14 days' notice, it is allowed once a month, and it cannot be cancelled. A wrong automated write would be costly.

- **Per-result event:** the Actor charges with Apify's synthetic `apify-default-dataset-item` event, which charges once for each item written to the dataset. Keep `apify-actor-start` at Apify's default price, and add no other per-result event, or each result would be charged twice.
- **Where the values come from:** the Builder writes the price into `actors/<name>/.actor/pricing.json` (the Validator's planned price, Q5). The Publisher prints those values in the "Publish <name>" issue for you to copy.

### Q15. Safety setup the Builder needs from you (open)

1. **Install the Claude GitHub App** on this repository: https://github.com/apps/claude. Without it the Builder workflow cannot run.
2. **Recommended: protect `main`** (Settings → Branches → add a rule for `main` that requires a pull request before merging). The Builder is told never to push to `main` and is denied force-pushes and `gh pr merge`, but the app has write access. Branch protection makes "only you merge" a rule GitHub enforces, not just an instruction.

### Q16. The Builder's model and cost (assumed)

The Builder runs Claude Code with `claude-opus-5-5`, with at most 120 turns and a 90-minute job timeout (`builder` in `config.yaml`). Building and testing one Actor is long agentic coding work, where the most capable model is worth its price. One build should cost a few dollars, but that is a guess until the first one runs. To try a cheaper run, set `builder.model` to `claude-sonnet-5-5`.

### Q17. Candidates whose only open point is unclear terms (resolved 2026-10-25: 🔎 REVIEW)

On the first live data, every strong candidate failed only because Claude found no sentence that explicitly grants commercial reuse. Most official public APIs simply publish their data without saying so. Such a candidate is now marked **🔎 REVIEW** instead of failing, but only when all of this holds:

- **Other checks:** Demand, Competition, Cost and Stability pass.
- **Access:** the data comes from an official API or public feed (`validator.legality.review_access`).
- **Login:** none is needed. "Unclear" does not count.
- **Personal data:** none, or only removable personal data while Q6 allows it.
- **robots.txt:** it allows the sample URLs.
- **Terms:** they neither forbid the use nor were shown to allow it with a cited passage.

The brief lists REVIEW candidates in their own section, with the passage and link Claude found. A REVIEW candidate never builds by itself:

- **To build one:** read the terms, then comment `/build <niche-id> terms-reviewed`.
- **Without the flag:** the Builder refuses.
- **The flag's limits:** it cannot rescue a candidate that failed any rule.

In the Actor's README, the Builder links the terms and does not claim they explicitly allow the use. To go back to the strict rule, set `validator.legality.review_unclear_terms: false`.

On the 2026-10-24 rehearsal data, this turned 2 of 40 candidates into REVIEW: Greenhouse Jobs API and Sitemap Extractor.

### Q18. Niches that can never pass (resolved 2026-10-25)

In week 43, 31 of the 40 assessed niches were scrapers of big platforms (Google, Amazon, ChatGPT, G2, Indeed and others) that the Validator rejects every week. Two changes free the Validator's slots for niches it has not ruled out:

- **Platform list:** `scout.exclude.platforms` lists those platforms. It is matched like `title_words`.
- **Memory:** a niche that failed Legality for a reason no build can fix is skipped for `scout.history.skip_hard_fails_weeks` (12) weeks. Those reasons are:
  - it needs a login
  - its data is personal data
  - its terms forbid the use
  - robots.txt disallows it
- **Where the memory lives:** each Validator brief carries the list as hidden JSON (`factory:validator-hard-fails`): that week's failures plus the ones still active, each dated. Scout reads the weekly issues of the last 12 weeks (titles starting "Scout "). If GitHub cannot be read, nothing is skipped and the run warns.
- **What doesn't count:** "unclear" answers, removable personal data and Cost or Stability failures. A niche that failed only for those comes back the next week.
- **To give a niche another chance:** remove its entry from the latest brief's hidden list, or set the weeks to 0.

### Q19. A robots.txt that answers 401 or 403 (resolved 2026-10-30: follow RFC 9309, the owner accepts it)

Ashby's public job posting API (`api.ashbyhq.com`) answers `/robots.txt` with **401 Unauthorized** instead of publishing a file. Ashby was checked on 2026-10-26 as a third platform for the Greenhouse & Lever Actor.

- **RFC 9309 (§2.3.1.3):** a robots.txt that is "unavailable" (any 4xx) means a crawler *may* access the site.
- **The template's `robots.py` is stricter:** only 404 and 410 count as "no robots.txt". Any other status, including 401 and 403, means the whole site is skipped. The rule is "never fetch a page you cannot show you are allowed to".
- **Conservative choice:** keep the strict rule, so the Actor does not support Ashby.
- **To decide:** if you accept RFC 9309's reading for 401 and 403, `robots.py` changes in the template and in each Actor, and Ashby can be added. 5xx and network errors would still skip the site.
- **Decision (owner, 2026-10-30):** follow RFC 9309. Any 4xx answer to `/robots.txt` means there is no robots.txt, so nothing is disallowed. 429, 5xx and network errors still mean "unreachable", so the site is skipped.
  - The rule applies in the Actor template's `robots.py`, in `actors/greenhouse-jobs-scraper`, and in the Validator's robots check.
  - Ashby's terms are a separate question. Its API docs describe it only as a way to fill a company's own careers page, and say nothing about third-party use.
  - **Owner decision on Ashby's terms (2026-10-30):** reviewed and accepted, as a REVIEW-style approval (Q17). Ashby boards were added to the Greenhouse & Lever Actor. As conservative limits, the Actor returns a salary only when the company shows pay on its posting (`shouldDisplayCompensationOnJobPostings`), and it leaves out jobs marked `isListed: false`.


### Q20. Crowded niches, generic tools and a twice-weekly Scout (resolved 2026-10-30: owner approved)

Five days after launch, `guayox/greenhouse-jobs-scraper` had no users outside the owner. It ranked outside the top 100 in Store search for "greenhouse", "greenhouse jobs" and "lever jobs". The W43 Validator had passed Competition because Scout's title clustering found few rivals. The real Store search finds 86 Actors whose title holds "greenhouse" and "job", most of them recent clones with almost no users. A new Actor in such a niche is buried. W43 also spent many of its 40 assessments on generic tools (integrations, downloaders, bypassers, runners) that have no single target site, so they can never get past Legality.

The owner approved three changes. The thresholds live in `config.yaml`.

- **Same-name Actors (`validator.competition.max_same_name_actors: 15`):**
  - Scout runs one Store search per niche for the best `scout.store_search.pool` niches. It counts the results whose whole title holds every niche keyword; the owner's own Actors are not counted.
  - Niches above the limit are left out before validation. The Validator's Competition check also fails them, whatever the leader's weaknesses.
  - A failed search counts as unknown, which is a fail.
  - Measured on 2026-10-30, these were crowded: greenhouse job 86, wayback machine 87, sitemap 76, universal 60. These were open: fuel prices 1, PageSpeed audit 8, Kalshi weather 19, Idealo 34.
  - The limit of 15 is a judgment call. Raise it if too few niches survive.
- **Generic tools (`scout.exclude.generic_tools`):**
  - Matched like the other exclusion lists.
  - Listed words now match their plurals too. "threads" and "onlyfans" in `title_words` had never matched, because niche keywords are singular.
- **Twice a week (Sundays and Wednesdays at 05:17 UTC):**
  - Issues are named by date (`Scout 2026-11-04: 20 candidate niches`) instead of ISO week, because a Wednesday and the following Sunday share an ISO week.
  - Every brief lists the niches it assessed (`factory:validator-assessed`). Scout skips them for `scout.history.skip_assessed_days` (28) days, so the Wednesday run brings new niches instead of paying to assess the same ones.
  - A PASS or REVIEW niche can still be built from the issue that listed it.
  - Validator spend roughly doubles, since there are two runs of up to 40 assessments a week.
- **Not changed:** `docs/SPEC.md` still says weekly. This entry records the owner's change.
