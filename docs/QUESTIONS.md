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


### Q20. Crowded niches, generic tools and a twice-weekly Scout (resolved 2026-10-30: owner approved; weekly again from 2026-11-01, Q26)

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

### Q21. More ATS platforms for the jobs Actor (resolved 2026-10-31: Workable and Personio added)

The 2026-10-30 Scout run found nothing buildable: 28 of 40 niches failed Legality for good, and the rest had little demand. Open-data niches proved just as crowded, for example SEC EDGAR with 76 same-name Actors and 134 users in total. The owner chose to win the jobs niche instead. There, the most-used Actors (85–136 users a month) each cover four or more ATS platforms, while single-platform Actors stay around 10 users.

Five platforms were checked on 2026-10-31:

| Platform | Result | Reason |
|---|---|---|
| Workable | Added | Workable's help centre documents a no-key public endpoint, `www.workable.com/api/accounts/<account>?details=true`. It redirects to `apply.workable.com/api/v1/widget/accounts/<account>`, whose robots.txt allows everything. The feed has no salaries. |
| Personio | Added | Personio's developer docs describe the XML feed at `<company>.jobs.personio.com/xml`. robots.txt allows everything for hosted companies; for names it does not host, it answers `Disallow: /` and the Actor skips them. The feed includes salary ranges where published. |
| SmartRecruiters | Not added | `api.smartrecruiters.com/robots.txt` disallows every crawler except LinkedInBot. |
| Recruitee | Not added | Its docs say the Careers Site API needs a company-issued token from 10 February 2027, so a third-party Actor would stop working. |
| Teamtailor | Not added | The API needs the company's own key. |
| Workday | Not added | The career sites use an internal, undocumented API. W43 already failed it on Cost and Stability. |

Workable's and Personio's docs describe these feeds for publishing a company's own jobs, and say nothing either way about third-party use. The owner reviewed this and approved both on 2026-10-31, as for Ashby (Q19).

### Q22. Assessing 80 niches per Scout run (resolved 2026-10-31: owner approved; back to 40 from 2026-11-01, Q26)

The 2026-10-30 run assessed 40 niches and none passed: 28 failed Legality for a reason no build can fix, and most of the rest had too little demand. Since most failures are legal, the number of passes depends mainly on how many niches are assessed. The owner approved raising `scout.candidates_to_validate` from 40 to 80, with `details.niche_pool` at 100 and `store_search.pool` at 250 to keep the pools in order.

- **Cost:** Validator spend roughly doubles per run, so with two runs a week it is about four times the original weekly plan.
- **Duration:** the 2026-10-30 run took 14 minutes (Scout 8.5, Validator 5.6). With 80 niches it should take about 25 minutes, inside the workflow's 75-minute limit.
- **Revisit** after a few runs. If the extra 40 niches rarely produce a PASS or REVIEW, lower the number again.

Measured the same day: the owner had asked for spin-off Actors from the jobs engine. Store demand for job change monitors (39 users a month in total), hiring signals (146), salary benchmarks (11) and layoff trackers (32) is too small to build for.

### Q23. A remote jobs Actor (decided 2026-10-31: not built, terms)

"Remote jobs" has real Store demand: about 1,160 users a month in total, and the two leading Actors have 200 and 193. Several remote job boards publish free APIs, so the owner asked for a terms check before building an aggregator. The terms were read on 2026-10-31:

| Source | Result | Deciding text |
|---|---|---|
| RemoteOK | Fails | robots.txt disallows crawlers. The API notice says "If you do not [link back] we'll have to suspend API access". |
| Remotive | Fails | The API's legal notice says "Please do not submit Remotive jobs to third Party websites". |
| Himalayas | Fails | API terms, clause 113(c) (himalayas.app/terms): "Show the jobs only on sites and apps you operate. Do not pass them on to third parties, such as other job boards, aggregators, job search engines…". An Apify Actor hands the jobs to its users. |
| Arbeitnow | Fails, conservatively | Terms section 2 (arbeitnow.com/terms) forbids using "the materials for any commercial purpose" and mirroring them. Section 11 on the API grants no commercial right and says "We may revoke the permission to use API at any time." |
| Jobicy | Passes | The API docs (jobicy.com/jobs-rss-feed) say: "You can store, cache, process, and redistribute job data as needed". They allow commercial use and aggregators, with credit to Jobicy, the Jobicy listing URL kept, and at most one sync per hour. |

Only Jobicy is clearly allowed. A Jobicy-only Actor would compete with aggregators that cover 6–8 boards, so it would lose on breadth. Actors that mention Jobicy have 418 users a month in total, most of them going to one multi-board aggregator. **Decision:** not built. Revisit if more remote boards publish permissive API terms.

### Q24. A tool lane, and tools that return the user's own data (resolved 2026-10-31: owner approved both)

The factory was built to find scraping niches. Its Legality check needs a target site whose terms and robots.txt it can read, so Actors that process the user's own data had no way to pass, and Q20 excluded them. Store demand was measured on 2026-10-31:

- **Data validation, cleaning and dataset review:** almost no demand (1–35 users a month in total per type). Merging and deduplicating datasets has 323, but one Actor takes 254.
- **Tools with demand:**
  - PDF text extraction: 492 users a month, 84 same-name Actors.
  - Website audits (Lighthouse, SEO): 308–371.
  - OCR: 312.
  - Domain availability: 188.
  - URL status and broken links: 166–188.
  - Website technology detection: 169.
  These are as crowded as scraping niches. They are simpler legally, though, and no site redesign can break them.

**Decision 1, the tool lane:**
- The Validator reports `kind` (scraper or tool) and, for tools, `outside_service`:
  - `none`: the tool processes only the user's input, including files at URLs the user gives.
  - `official_api`: the tool calls a documented outside API.
  - `user_websites`: the tool checks websites the user names.
- A tool with `none` or `user_websites` passes Legality without a site's terms or a robots.txt check up front. A `user_websites` tool must check each site's robots.txt at run time, which the template does. Stability passes because the tool depends on no site's layout.
- A tool that calls an outside API is judged like a scraper: that API's terms and robots.txt decide.
- The hard rules stay for both lanes: no login, and no personal data collected from anyone but the user.
- `scout.exclude.generic_tools` now lists only what the factory never builds: anti-bot evasion, traffic generators, media downloaders, account integrations, scraping and code infrastructure, and scrapers of "any" site. PDF, HTML, URL, screenshot and sitemap tools go to the tool lane.

**Decision 2, the user's own data (`validator.legality.allow_user_supplied_personal_data: true`):**
- A tool with `outside_service: none` may return the user's input unchanged, personal data included, for example the text of the user's own PDF.
- Such an Actor names the fields that carry the input in the template's `USER_SUPPLIED_KEYS`, and the privacy guard leaves only those fields unchanged.
- Personal data from websites, even websites the user named, is never treated as the user's own.

### Q25. Publishing new Actors without the Console (resolved 2026-10-31: owner approved test run + publish)

The owner wants new Actors fully set up through the API, so they "virtually don't even have to log in". Asked how far the Publisher should go after a merge, the owner chose test run plus publish.

- **Pricing:** created by the Publisher while the Actor is private, from `pricing.json` with `managedByPublisher: true`. Bronze, Silver and Gold discounts come from `publisher.default_tier_discounts` unless `tiersPer1000Usd` is set. Apify applies pricing at once when an Actor has no paying users. Afterwards the Publisher only lowers prices; increases stay in the Console.
- **Publishing:** the owner's merge is the approval. The Publisher then runs the Actor once with its prefilled input. If that run succeeds with at least one result within `publisher.test_run_timeout_seconds` (300, Apify's daily-test limit), the Publisher makes the Actor public and publishes its tasks. It never publishes an Actor without pay-per-event pricing, so nothing goes public free. Any failure leaves the Actor private and opens a "Publish <name>" issue with the reason and the run link.
- **Turn it off:** set `publisher.auto_publish: false`.
- **Still manual:** the Store icon, because Apify's API does not accept one. The "is live" issue reminds the owner.

### Q26. A weekly Scout of 40 niches (resolved 2026-11-01: owner approved)

Three full runs found no buildable niche: 2026-10-25, 2026-10-30 (40 assessed) and 2026-11-01 (80 assessed). Each run skips niches already assessed or blocked, so later runs reach weaker ones. The 2026-11-01 run used about 3.7 million input tokens (almost all cached), 96,000 output tokens and 87 web searches. Asked to cut the cost before the January checkpoint, the owner chose a weekly run of 40.

- `scout.yml` runs on Sundays at 05:17 UTC. GitHub may start a scheduled run hours late, or skip it on a busy day; the Actions tab can start one by hand (**Run workflow**).
- `scout.candidates_to_validate: 40`. The pools (`details.niche_pool` 100, `store_search.pool` 250) stay, so the order check still holds.
- `scout.history.skip_assessed_days` stays at 28: four weekly runs of new niches before one comes back.

### Q27. Reporting removed jobs (decided 2026-11-01: opt-in, charged as results)

The owner asked for a feature that reports jobs that disappeared since the last run, after the 2026-11-01 Scout found an "Expired Jobs API" with users but a source that failed Legality. Open questions and the conservative choices made:

- **Opt-in.** The input `reportRemoved` is off by default, so no existing run or schedule changes what it returns or costs.
- **Charged as results.** Each removed job is one dataset item, charged with the existing `apify-default-dataset-item` event at the same price. Nothing is added to the pricing, so it is not a pricing change on Apify. The input description, the README and the pricing section say so.
- **No false closures.** Removed jobs are reported only by a run that read every board, and only for boards that answered in that run. A board that fails keeps its jobs in the memory. This also fixes an older bug: with "Only new jobs" on, a board that failed for one run had its jobs returned, and charged, again on the next run.
- **Filters.** A job whose title or location no longer matches the keywords counts as removed, because the memory follows the search. The README describes removed jobs as "no longer listed" for the search.
- **Old memories.** Records written before this change (a list of keys) still work. Jobs removed from them have no title or link, only platform, board and job ID.

### Q28. Pausing the Scout (resolved 2026-11-07: owner approved)

Four full runs (2026-10-25, 10-30, 11-01, 11-07) found no buildable niche, and each run skips what it has seen, so it reaches weaker niches. The owner turned the schedule off.

- The Scout workflow is disabled in GitHub (`gh workflow disable scout.yml`). The file still has its Sunday cron. **While disabled it can't be started by hand either**; `gh workflow enable scout.yml` undoes it.
- The 2026-11-07 run used about 2.2 million cached input tokens, 16,000 uncached input tokens, 54,000 output tokens and 49 web searches.

### Q29. One last bet: job search without naming companies (resolved 2026-11-07: owner approved, with a stop rule)

The market leader, Career Site Job Listing API, has 1,635 monthly users at prices from $4 per 1,000 jobs. Its users search by title and location across 275k+ career sites without naming a company. Our Actors need the company names. Among smaller Actors the evidence is thin and mixed: optional ready-made lists 87 monthly users (`bovi`), companies required 9 (`automation-lab`), a curated list at $4 per 1,000 0 (`benthepythondev`).

**Stop rule, agreed with the owner:** on 2027-01-03, with fewer than 5 outside users, building stops and the Actors stay live and idle. No more pivots.

**Checks made before building (2026-11-07):**

| Source of board names | Terms | Result |
|---|---|---|
| Common Crawl index | No ban on commercial use, no permission either; "strongly recommends" legal advice before use | 5,101 candidate boards. 60-board samples: Greenhouse 59 live, Ashby 59, Personio 39, Workable 32; none usable for Lever. Roughly 3,400 live boards and 120,000 jobs |
| Wikidata software companies | CC0 | 0 of 50 names had a live board on Greenhouse, Ashby or Personio |
| A hand-made list of well-known companies | No third-party data | 24 of 30 names had a live board, 4,534 jobs (a famous-name sample, so the long tail will be smaller) |

The conservative choice is the hand-made list, checked against the official feeds. It excludes pharma and health companies because of the owner's contract.

**Cost:** reading a board takes about 1 second, because each host is limited to one request per second. Scanning on every search would be charged to the owner (the jobs Actor passes no platform usage to users) and could cost more than the search earns: at 1 GB and $0.40 per compute unit, 10 minutes costs about $0.07, while 50 jobs earn about $0.04. So searches need a prepared index, refreshed on a schedule, with only the boards that match read live. 

**Design, after checking Apify's storage docs:** a named key-value store never expires and can be read by ID without a token, so a user's run can read it. `directory.yml` rebuilds it daily in GitHub Actions: only board names, job titles and locations, no descriptions. A search will use it to choose boards, then read only those live, so the jobs returned are live and the index can miss at most a day of new jobs. Apify's docs don't say who pays when another user reads a store, or give a record size limit beyond a 9 MB request example, so the build refuses anything bigger; check both once it runs.

**Rate limits:** after the 60-board sample, at about one request per second, `apply.workable.com` answered HTTP 429 to the test machine on both its feed and its robots.txt. The Wikidata run also read no Workable boards, so that row has no Workable result. An index must read Workable far more slowly, or read fewer Workable boards, and must treat a 429 as "not read", never as "jobs removed".

**First real build (2026-11-07):**

| Measure | Result |
|---|---|
| Names with open jobs | 278 of 531 |
| Index | 275 boards, 28,854 jobs, 0.29 MB compressed, readable by ID with no token |
| By platform | Greenhouse 156 boards, Ashby 93, Lever 21, Personio 5, Workable 0 |
| Build time | 33 minutes |

- **Workable:** it answered 429 again at one request per 5 seconds, so the build stopped it after 304 of 531 names. It adds no boards for now; the 2 boards it found weren't read when the index was built.
- **Size against the market:** 275 boards is about 0.1% of the leader's 275k+ sites. The search competes on price and MCP access, not on coverage, and the listings say so.
- **Still to check:** who pays when another user's run reads the store.

### Q30. MCP directories (resolved 2026-11-07: owner approved)

The project rule is "no outreach of any kind". The owner decided that listing an MCP server in MCP directories is allowed, because no one is contacted. Posts and messages stay excluded.

- **Official MCP Registry:** first choice. It accepts closed-source servers that are publicly reachable, and removes only illegal content, malware, spam and broken servers. `mcp-registry.yml` publishes `docs/mcp-registry/server.json` using GitHub OIDC, so no secret is needed. The entry stays visible through the registry's API even after removal.
- **Glama:** not used for now. Third-party sources say it indexes public GitHub repositories and needs a local server; this repository is private and the server is remote only.
- **Others (Smithery, PulseMCP):** not checked against their own documentation yet.
