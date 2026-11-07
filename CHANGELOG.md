# Changelog

## 🎯 MCP server: a company name finds the right board (2026-11-07, branch `mcp-pick-right-board`)

- **Bug:** for a plain company name, the server stopped at the first platform with any open jobs, and Greenhouse is tried first. Live on 2026-11-07:
  - "ramp" returned one job, "Copy of Chief Legal Officer", from a Greenhouse board named RAMP, while the Ashby board has 171;
  - "warp" went to a 5-job Greenhouse board, so the README's "account executives" example returned nothing, while the Ashby board has 4 matches.

  Users would have paid for those wrong results. The tests missed it because their saved data had no second board under the same name.
- **Fix:** a plain name now reads all five platforms and uses the board with the most open jobs (the earlier platform on a tie). Any other boards found come back as `other_boards`, because a smaller board can still be the company the user means. An explicit key or URL reads only that board.
- **Speed, measured live:** about 5 s for the first company and about 2 s per company after that (20 s for 10 companies). An explicit key took about 1 s.
- **Docs:** tool descriptions, server instructions, README and a new FAQ entry. MCP Actor 0.4.
- **Tests:** 136 MCP Actor tests (3 new).

## 📏 Tasks no longer cut off at 1,000 jobs (2026-11-01, branch `task-result-caps`)

- **Why:** the owner ran the MCP Actor's new task and got exactly 1,000 results. The 12 boards have about 1,670 open jobs (Stripe alone has 745), so the run stopped partway through Zoox. Spotify, Notion, Ramp, Warp, Hugging Face, Blueground, ottonova and tado were never read.
- **Tasks:** "Maximum results" goes from 1,000 to 3,000 in the three tasks that promise every job at the 12 companies: daily-new-tech-jobs, new-and-closed-tech-jobs and tech-jobs-and-salaries-snapshot. The filtered remote-engineering task keeps 500.
- **Both Actors:** a run that hits "Maximum results" now logs a warning that later boards were not read. Its status message ends with "Stopped at Maximum results: raise it to get every job." Before, a capped run looked complete.

## 🧩 MCP Actor: a published task, and what its health warning means (2026-11-01, branch `mcp-task`)

- **Why:** the MCP Actor's quality score is 68, against 82 for the jobs Actor. Insights flagged "Publish a task", "Fix Actor health issues" and "Grow your user base".
- **Task:** `tasks.json` adds "Open jobs and salaries at 12 tech companies", a normal run of the same five ATS feeds. The Publisher creates and publishes it after the deploy. The README points to it.
- **Health warning: no code change.**
  - The Debugging tab shows no user runs, and the owner's only run succeeded.
  - Apify's daily test skips Actors with Standby enabled and those in the MCP servers category, so there was no test run either.
  - The Store's 0.0% success rate and the warning therefore had no runs to measure; they should clear once real users run the Actor successfully.
  - `docs/seo/ats-jobs-mcp-server.md` records this in its baseline row.
- **"Grow your user base"** asks for promotion in communities, which is outreach; the factory does none.

## 🔔 Jobs Actor: report filled and closed jobs (2026-11-01, branch `removed-jobs`)

- **Why:** the 2026-11-01 Scout found an "Expired Jobs API" whose source failed Legality. Our jobs Actor already remembers what earlier runs returned, so it can report closed jobs from the official feeds. Recruiters, sales teams and investors read that as a hiring signal (Q27).
- **New input `reportRemoved` (off by default).** Each run also returns the jobs earlier runs returned that are no longer listed, once each, marked `change: "removed"`, with title, company, location, department and link.
  - Every job is marked `new` or `open`.
  - A removed job is one result at the usual price; no pricing change.
- **No false closures.** Removed jobs are reported only by a run that read every board, and only for boards that answered.
  - **Bug fixed:** with "Only new jobs" on, a board that failed for one run used to have all its jobs returned, and charged, again on the next run.
- **Memory:** now keeps a short summary per job. Old memories (a plain list of keys) still work.
- **Output:**
  - a `change` field;
  - a "New and removed jobs" dataset view;
  - a third published task, "New and closed jobs at top tech companies (hiring signals)";
  - a README section, "How to track filled and closed jobs (hiring signals)".
- **The MCP Actor** shares the code (`source.py`, `seen.py`, `collect()`), so its normal runs get the option too.
- **Versions:** jobs Actor 0.6, MCP Actor 0.3.
- **Tests:** 125 jobs Actor tests and 133 MCP Actor tests (5 new in each): removed jobs reported once, failed boards keep their jobs, runs stopped early report none, old memories.

## 📉 Scout weekly, 40 niches (2026-11-01, branch `scout-weekly-40`)

- **Why:** three full runs found no buildable niche, so the owner cut the Scout's Claude cost to about a quarter before the January checkpoint (Q26).
- **Changes:**
  - `scout.yml` runs on Sundays only.
  - `scout.candidates_to_validate` goes back from 80 to 40.
  - README, CLAUDE.md, QUESTIONS (Q20, Q22, new Q26) say so.

## 🎯 MCP server: CV matching and a use-case listing (2026-10-31, branch `mcp-skills-use-cases`)

- **Why:** CV-to-jobs matching is a real need, but as a separate Actor it would have almost no buyers. The five Store Actors that do it have at most 4 monthly users, and job seekers use free consumer apps. Through our MCP server, the user's own AI assistant reads the CV and does the matching on its own subscription. We pay no AI cost and charge per job returned.
- **`search_jobs` takes `skills`:**
  - it keeps jobs whose title or description mentions at least one skill, ranked by how many, each with `matched_skills`;
  - matching is whole-word and ignores case ("Go" is not "good", "C" is not "C++");
  - with skills, it reads descriptions and every listed company before ranking;
  - only the jobs returned are charged.
- **Listing:**
  - Title "Job Search MCP Server: Greenhouse, Lever, Ashby & More".
  - New SEO title and description.
  - The README gains a use-case table with ten uses (CV matching, salary research, competitor hiring, hiring signals, tech stack from job posts, ATS lookup and more), a "What it does not do" paragraph and a CV-matching section.
  - Version 0.2. The jobs Actor's links use the new name.
- **New `docs/seo/ats-jobs-mcp-server.md`:** target search phrases per use case, where each appears, and a results table with a 2026-10-31 baseline (1 user, 0 monthly, 0.0% success rate) and review dates.
- **Tests:** 128 MCP Actor tests (2 new).

## 🚀 New Actors go live without the Console (2026-10-31, branch `publisher-auto-publish`)

- **Why:** the owner wants every aspect of a new Actor set through the API (Q25).
- **After the owner merges a new Actor, the Publisher:**
  1. deploys it and sets title, description, SEO text and categories (as before);
  2. **creates its pay-per-event pricing** while it is private, with Bronze, Silver and Gold discounts (default 10/20/30% from `config.yaml`);
  3. **test-runs it** with the prefilled input; the run must succeed with results within 300 s, as in Apify's daily test;
  4. **makes it public** and publishes its tasks, then opens a "✅ live" issue whose only remaining step is the icon. Apify's API accepts no icons.

  If any step fails, the Actor stays private, and the issue says why, with the run link. It never publishes without pricing. `publisher.auto_publish: false` turns it off.
- **New `factory/publisher/publish.py`.** `pricing.py` can create a private Actor's first record, but still never raises a price.
- **Template:** `pricing.json` with `managedByPublisher: true`, and a new `tasks.json`. `docs/BUILDER.md` asks for 1–2 tasks and a prefill that returns results.
- **Tests:** 278 factory tests (6 new): first pricing, publish only after a successful run with results, no publishing without pricing, Apify refusals.

## 💲 Publisher lowers prices from pricing.json; jobs Actor to $0.99 (2026-10-31, branch `publisher-pricing`)

- **Why:** several career-site Actors charge $0.99–1.15 per 1,000 jobs. With no paying users yet, the owner chose to cut the jobs Actor from $1.60 to $0.99, and preferred a PR to the Console.
- **New `factory/publisher/pricing.py`:** opt-in per Actor with `"managedByPublisher": true` in `pricing.json`. After each deploy, the Publisher compares the price with Apify's current pricing record.
  - It sends Apify's pricing history unchanged plus one new record starting now.
  - It only ever lowers prices, or updates titles and descriptions. Increases, new paid events and model changes are refused with a warning. Apify treats those as significant changes: 14 days' notice, once a month, and they can't be cancelled.
  - Prices outside `publisher.price_per_1000_bounds` ($0.10–10 per 1,000, in `config.yaml`) are refused, so a typo can't multiply the price.
  - A rejected update only warns, and the deploy still succeeds.
- **Jobs Actor:** $0.99 per 1,000, with tier discounts of $0.89 (Bronze), $0.79 (Silver) and $0.69 (Gold, also Platinum and Diamond). The event description now reads "company job board". README and SEO description updated. The MCP server stays at $1.60 and is not managed.
- **Tests:** 272 factory tests (7 new), run against the jobs Actor's real pricing history.

## 🏷️ Jobs Actor repositioned for "career site" searches (2026-10-31, branch `career-page-seo`)

- **Why:** buyers search for "career site" and "career page" jobs, not "ATS". The biggest Actor in the space, "Career Site Job Listing API", has about 1,660 users a month, and a "Job Search Scraper – Direct from Company Career Pages" charges $5.00 per 1,000 to 140 users. Our jobs Actor did not appear for those searches.
- **Change** (the URL stays `greenhouse-jobs-scraper`):
  - Title: "Career Site Jobs Scraper: Greenhouse, Lever, Ashby & More". New description.
  - SEO title "Career Site Jobs API: Greenhouse, Lever, Ashby, Workable", and an SEO description with the price.
  - New README section "Jobs straight from company career pages", and the H1 and first paragraph use the phrase.
  - The MCP server's cross-link uses the new name.
- **Checked:** our $1.60 per 1,000 is not the lowest. Several career-site Actors charge $0.10–1.15, so the README states the price without comparing.

## 📋 Publisher creates and publishes saved tasks (2026-10-31, branch `publisher-tasks`)

- **Why:** Apify's quality score for the jobs Actor (78/100) asks for a published task. The owner preferred a PR to setting it up by hand.
- **Change:**
  - New convention `.actor/tasks.json`, plus `factory/publisher/tasks.py`. After each deploy, the Publisher finds each task by `owner~name` and creates or updates it (title, description, input, options).
  - Tasks marked `publish` are published in a second request, so a refused publish leaves the task in place and only warns, with Apify's reason. The Actor must be public, and `publicConfig` must name the input fields and a dataset view.
- **Jobs Actor tasks:** "Daily new jobs at top tech companies" (12 boards on all five platforms, `onlyNew`) and "Remote engineering jobs with salaries" (same boards, filtered).
- **Tests:** 265 factory tests (4 new). A check keeps every task to the Actor's own input fields, its dataset views and Apify's limits.

## 🔎 Store visibility: README headings, cross-links, icons (2026-10-31, branch `readme-visibility`)

- **Why:** a week after launch, the jobs Actor ranked outside the top 100 for "ATS jobs", "Greenhouse jobs" and "Lever jobs". Its Actor quality score is 78/100. The README and reliability already rank in Apify's top 15% and 1%; the open items are an icon, Store discounts and a published task. Apify says search ranking correlates strongly with the quality score.
- **Jobs Actor README:**
  - New section "Supported job boards" with an H3 per platform ("Greenhouse jobs scraper", "Lever jobs scraper" and so on). Apify notes that H2 and H3 headings can show in Google results.
  - The pricing heading is now a question.
  - A "Related Actors" section links the MCP server.
- **MCP server README:** headings name the Actor, and "Related Actors" links back to the scraper. Apify recommends Actors within a category, so the two lift each other.
- **Template and `docs/BUILDER.md`:** a "Related Actors" section and rules for search-phrase headings, so every future Actor launches with them.
- **Icons:** `docs/store-icons/` holds a 512×512 icon for each Actor, for the owner to upload in Apify Console.

## 🤖 ATS Jobs MCP Server, the second Actor (2026-10-31, branch `ats-jobs-mcp`)

- **Why:** AI agents increasingly call Apify Actors as tools. MCP servers have about 890 users a month on the Store, and the goal names AI agents as a sales channel. A separate Actor gets its own "MCP" listing, counts toward Phase 2, and leaves the live jobs Actor's pricing alone.
- **New Actor `actors/ats-jobs-mcp-server`:**
  - It shares the jobs scraper's tested code. A factory test keeps `source.py`, `polite.py`, `robots.py`, `privacy.py` and `seen.py` identical in both Actors.
  - Standby mode (`usesStandbyMode`, `webServerMcpPath: /mcp`) serves MCP over Streamable HTTP with the official MCP Python SDK 2.x (`MCPServer`). It answers Apify's readiness probe on `/`.
  - The SDK's localhost-only host check is switched off, because requests arrive through Apify's public Standby URL.
  - Tool `find_job_board` (free) tries the five platforms for a plain company name. Tool `search_jobs` returns filtered jobs, each pushed to the dataset and so charged ($1.60 per 1,000). It stops at the user's spending limit.
  - A normal run, including Apify's daily test, reads the input's boards like the jobs scraper.
- **Store text:**
  - Title: "ATS Jobs MCP Server: Greenhouse, Lever, Ashby & More". Categories: Agents and Jobs.
  - The README covers connecting from Claude Code and any MCP client.
- **Tests:** 126 Actor tests, 6 of them new: tools, charging, the spending limit, and the HTTP app with a public host. A live local Standby run found that Notion uses Ashby (148 open jobs) and returned Airbnb engineering jobs with salaries.

## 🔁 "Only new results" for every Actor (2026-10-31, branch `only-new-items`)

- **Why:** the jobs Actor has no repeat users. Scheduled runs that return only what is new turn one-off users into daily runs, which is recurring revenue, and repeat runs are what Store ranking rewards.
- **Template** (every future Actor):
  - New `seen.py`. It remembers returned items in a named key-value store in the user's account, which survives between runs.
  - `main.py` skips items an earlier run with the same search returned. They are neither pushed nor charged.
  - Input fields `onlyNew` and `monitorName`. `source.py` gets `item_key()` and `Settings.state_key`.
  - A run that stops early (maximum results or spending limit) keeps the items it did not reach for the next run. Only a complete run forgets items that disappeared.
  - The README has a "feed of new results" section, and `docs/BUILDER.md` tells the Builder to keep the feature.
- **Jobs Actor:**
  - "Only new jobs" uses a job key of platform, board and job ID. The memory follows the boards and keywords, or the user's monitor name.
  - The README has a new section, "Get a daily feed of new jobs".
- **Tests:** the template's tests (33) and the jobs Actor's tests (120) include end-to-end runs in sequence that share local storage, as scheduled runs do.

## 🧰 Tool lane: Actors that process the user's data (2026-10-31, branch `tool-lane`)

- **Why:** the owner asked to look beyond scraping. Tools have real demand: PDF extraction (492 users a month), website audits (308–371), OCR (312), URL and link checks (166–188). The Validator could not judge them, because it needs a target site's terms (Q24). Data validation and review on their own have almost no demand.
- **Validator:**
  - New facts: `kind` (scraper or tool) and `outside_service` (none, official_api, user_websites), plus a `user_supplied` value for `personal_data`.
  - A tool that reads no single site passes Legality and Stability without site terms. Login and third-party personal data still fail.
  - A tool that calls an outside API is judged like a scraper.
  - Older saved assessments load as scrapers.
- **Owner decision:** a tool may return the user's own input unchanged, personal data included (`allow_user_supplied_personal_data`). It names those fields in the template's new `USER_SUPPLIED_KEYS`, and the privacy guard leaves only them unchanged.
- **Scout:** `generic_tools` keeps only what is never built: evasion, traffic generators, downloaders, account integrations, scraping and code infrastructure, and scrapers of "any" site. PDF, HTML, URL, screenshot and sitemap tools reach the Validator.
- **Builder:** the brief describes tools and the `USER_SUPPLIED_KEYS` rule. `CLAUDE.md` and `docs/BUILDER.md` state the exception.
- **Tests:** 260 factory tests (10 new) and 31 template tests (1 new).

## 📝 Remote jobs Actor: checked, not built (2026-10-31, branch `q23-remote-jobs`)

- **Why:** "remote jobs" has real Store demand, so the owner asked for a terms check of five remote job board APIs.
- **Result:** only Jobicy's terms clearly allow redistribution. RemoteOK, Remotive, Himalayas and Arbeitnow forbid it or do not allow commercial use. A Jobicy-only Actor would lose on breadth to aggregators that cover 6–8 boards, so it was not built. Details and quotes are in QUESTIONS Q23.

## 🎯 Scout assesses 80 niches per run (2026-10-31, branch `scout-assess-80`)

- **Why:** the 2026-10-30 run assessed 40 niches and none passed. Most failures are legal and cannot be fixed, so more assessments mean more chances of a pass (Q22).
- **Change:** `scout.candidates_to_validate` goes from 40 to 80, `details.niche_pool` from 50 to 100, and `store_search.pool` from 200 to 250.
- **Cost:** about twice the Validator spend per run. The run should take about 25 minutes instead of 14.
- **Tests:** 250 factory tests.

## 🧩 Workable and Personio in the jobs Actor (2026-10-31, branch `ats-workable-personio`)

- **Why:** the 2026-10-30 Scout run found nothing buildable, and the owner chose to win the jobs niche. Buyers there choose breadth: the most-used Actors cover four or more ATS platforms (Q21).
- **Change** in `actors/greenhouse-jobs-scraper`:
  - Workable: `workable:<account>` or `apply.workable.com/<account>` URLs. The Actor reads the public jobs endpoint Workable documents, which gives company name, location, department, description and remote flag. There are no salaries.
  - Personio: `personio:<company>` or `<company>.jobs.personio.com` / `.de` URLs. The Actor reads the documented XML feed, which gives company, offices, department, description and the salary range where published.
  - The XML is parsed with the standard library and no external entities are resolved.
  - Checked and not added: SmartRecruiters (robots.txt blocks crawlers), Recruitee (token required from February 2027), Teamtailor (needs a key) and Workday (internal API).
- **Store text:**
  - Title: "ATS Jobs Scraper: Greenhouse, Lever, Ashby & More". SEO title: "ATS Jobs API: Greenhouse, Lever, Ashby, Workable, Personio".
  - The README has a platform table. Version 0.4.
  - The default input covers all five platforms.
- **Tests:** 118 Actor tests (22 new), with real fixtures (Blueground on Workable, tado on Personio). A live check returned 474 jobs from 7 boards in 12 s.

## 🧩 Ashby boards in the jobs Actor (2026-10-30, branch `ashby-boards`)

- **Why:** the owner accepted RFC 9309 for robots.txt (Q19) and reviewed Ashby's terms. Most competing multi-ATS Actors already cover Ashby, which is popular with fast-growing tech companies.
- **Change** in `actors/greenhouse-jobs-scraper`:
  - Input: `ashby:<company>` boards, or any `jobs.ashbyhq.com` or `api.ashbyhq.com/posting-api/job-board/` URL. Board names are not case-sensitive.
  - Source: one request per board to `api.ashbyhq.com/posting-api/job-board/<name>?includeCompensation=true`.
  - Output: the same fields as the other platforms. Employment type is readable (`Full-time`), and workplace type is `onsite`, `remote` or `hybrid`.
  - The salary range comes from Ashby's compensation summary, and only when the company shows pay on its posting.
  - Jobs the company keeps off its board list (`isListed: false`) are left out.
- **Store text:**
  - Title: "Greenhouse, Lever & Ashby Jobs Scraper". The description, SEO text and README are updated; the Publisher now sets these on deploy.
  - Version 0.3.
  - The default input adds `ashby:warp`, so Apify's daily test covers all three platforms.
- **Tests:** 96 Actor tests (11 new), with a real Warp fixture saved with `tests.fetch_fixture`; investor names are blanked. A live check returned 618 jobs from 4 boards: Airbnb 201 (164 with salary), Zoox 227 (211), Warp 20 (18) and Ramp 170 (163).

## 🤖 robots.txt: a 4xx answer means "no robots.txt" (2026-10-30, branch `robots-4xx-ashby`)

- **Why:** owner decision on Q19. Ashby's API answers `/robots.txt` with 401, and the old rule skipped such sites. RFC 9309 (§2.3.1.3) treats any 4xx answer as "unavailable", which means crawlers may access the site.
- **Change:** in the Actor template, in `actors/greenhouse-jobs-scraper` and in the Validator's robots check:
  - Any 4xx answer except 429 means no restrictions.
  - 429, 5xx and network errors still mean "unreachable": the Actor skips the site, and the Validator's Legality check stays unknown.
- **Not added yet:** Ashby. Its API docs describe the API only for a company's own careers page, with nothing about third-party use, so its terms wait for the owner's review.
- **Tests:** 250 factory tests (2 new), the template's and the Greenhouse Actor's robots tests now cover 401, 403 and 429.

## 🏷️ Publisher sets the Store listing (2026-10-30, branch `publisher-sync-listing`)

- **Why:** `apify push` deploys code but leaves the Store listing alone. The owner had to paste the title, description, SEO text and categories into Apify Console by hand. The Greenhouse & Lever Actor still had no category, so it did not appear in the Jobs category.
- **Change:** after each deploy, the Publisher sends the listing fields to Apify's Update Actor API (`PUT /v2/acts/<owner>~<name>`), which changes only the fields it is sent:
  - `title` and `description` come from `actor.json`.
  - `seoTitle`, `seoDescription` and `categories` come from `listing.json`.
  - Categories Apify Store does not know, checked against `scout.store.categories`, are left out with a warning.
  - A failed update is a warning, not a failed deploy.
- **First use:** this PR edits the Greenhouse Actor's `listing.json` comment, so merging it runs the Publisher. That sets the Actor's categories to Jobs and Automation.
- **Tests:** 248 factory tests (3 new).
- **Generic tools:** the first live dry run of the sharper Scout (2026-10-30) still let some developer tools through, because their names are single made-up words: Scrapeunblocker, Superscraper, Camoufox, jsdom, AI code sandbox, Claude Code and Video LLM analyzer. Their words were added to `scout.exclude.generic_tools`. That run searched 200 niches, left out 89 as crowded, and kept 40 candidates with 1 to 15 same-name Actors each.

## 🎯 Scout: skip crowded niches and generic tools, run twice a week (2026-10-30, branch `scout-sharper`)

- **Why:** five days after launch, the Greenhouse & Lever Actor had no outside users and ranked outside the top 100 in Store search. Its niche has 86 same-name Actors, which Scout's title clustering did not see. W43 also spent many assessments on generic tools that can never pass Legality. See Q20.
- **Crowded niches:**
  - Scout runs one Store search per niche for the best 200 niches. It counts Actors whose title holds every niche keyword, and leaves out niches with more than `validator.competition.max_same_name_actors` (15).
  - The Validator's Competition check also fails those niches, and fails niches whose count is unknown.
  - The issue's Data line shows how many niches were left out.
- **Generic tools:**
  - New `scout.exclude.generic_tools` list: integrations, downloaders, bypassers, runners, sitemap and similar.
  - Excluded words now match plurals. "threads" and "onlyfans" had never matched.
- **Twice a week:**
  - `scout.yml` runs on Sundays and Wednesdays.
  - Issues are named by date (`Scout 2026-11-04: …`), so two runs in one ISO week never share an issue.
  - Every brief lists the niches it assessed, and Scout skips them for `scout.history.skip_assessed_days` (28) days, so the second run brings new niches.
- **Tests:** 245 factory tests (9 new). A live dry run checked the Store search.

## 🩹 Greenhouse salaries and job boards typed on one line (2026-10-26, branches `board-list-input` and `greenhouse-salaries`)

- **Greenhouse salaries:** the Actor now adds `pay_transparency=true` to the same Greenhouse request, so it costs no extra requests.
  - Each job's first pay range fills `salary_min`, `salary_max` and `salary_currency`.
  - `salary_interval` is read from the range's name, for example "Mexico Monthly Pay Range". It stays `null` when the name does not say, as with a bare "Pay Range".
  - Coverage: 152 of 187 Airbnb jobs and 44 of 47 Discord jobs now carry a salary. Stripe publishes none.
  - Tests use a real fixture, `airbnb_jobs_pay.json`, saved with `tests.fetch_fixture`.
- **Boards on one line:** a first Console run of the Greenhouse & Lever Actor had `airbnb, lever:zoox` typed as one list entry. The Actor read it as a single unknown board, found nothing and exited with code 1.
  Each `boardTokens` entry is now split on commas, semicolons and line breaks; board tokens and URLs never contain them. Not on spaces, so a typed company name such as "Acme Corp" stays one invalid entry instead of becoming two other companies' boards. A plain string instead of a list also works. The input description says so.
- **Tests:** 85 Actor tests (2 new).

## 🧩 Greenhouse & Lever Jobs Scraper (2026-10-26, branch `ats-lever`)

- **Why:** "Greenhouse jobs" is crowded on the Store (about 25 Actors, 10 with nearly the same name). The Actors with real traction cover several applicant tracking systems.
- **Lever support** in `actors/greenhouse-jobs-scraper`:
  - Input: `lever:<company>`, `lever-eu:<company>`, or any `jobs.lever.co` / `jobs.eu.lever.co` URL, mixed freely with Greenhouse boards.
  - Source: one request per board to Lever's public Postings API. Lever's docs say published postings "may be scraped by third parties". Its robots.txt allows crawling with a 1-second delay.
  - New output fields `platform`, `employment_type`, `workplace_type`, and `salary_min`, `salary_max`, `salary_currency`, `salary_interval`. Greenhouse jobs carry them as `null`, and every existing field is unchanged.
- **Rate limit:** capped at 1 request per second (was up to 5) to honour Lever's crawl delay.
- **Store text:**
  - Title: "Greenhouse & Lever Jobs Scraper". The SEO title and description are updated, and the README is rewritten.
  - The default input is `airbnb` plus `lever:zoox`, so Apify's daily test covers both platforms.
  - Same price: $1.60 per 1,000 jobs.
- **Not added:** Ashby. Its API answers robots.txt with 401, which the factory's strict robots rule treats as "skip" (Q19).
- **Tests:** 83 Actor tests, against real Lever fixtures saved with `tests.fetch_fixture`. A live check returned 775 jobs from 4 boards in 16 s, 219 of them with salaries.

## 🔧 Smoother Builder runs (2026-10-25, branch `builder-tools`)

- **Why:** the first live build (issue #8, PR #11) hit 12 blocked commands. Each was harmless, and Claude worked around them, at the cost of extra turns.
- **Newly allowed:**
  - `rm`
  - `git reset`
  - `gh issue view` (read-only)
  - `PYTHONPATH=. python`
- **Still blocked:** `git -C <path>`, because it would slip past the push and force-push rules. `docs/BUILDER.md` now tells Claude to run git from the repository root, to write throwaway scripts to files instead of here-documents, and to loop in Python rather than in the shell.
- **Unchanged safety net:** the scope check still fails any PR that changes or deletes a file outside `actors/<name>/`.

## 🩹 Builder could not build live candidates (2026-10-25, branch `brief-keeps-buildable`)

- **Bug:** a live brief with 40 assessments is too long for one comment. The size guard then dropped every assessment from the hidden data, including those of PASS and REVIEW candidates. `/build greenhouse-job terms-reviewed` on issue #8 was refused with "the brief has no assessment details". The rehearsal used smaller sample data, so it did not show.
- **Fix:** the guard now drops failing candidates' assessments first, and drops those of PASS and REVIEW candidates only if the brief still does not fit.
- **`--reuse <validation.json>`:** the Validator can re-apply the checks to an earlier run's assessments without calling Claude again. Week 43's brief was re-posted this way, with the same facts and verdicts.
- **Tests:** 236 pass.

## 🎯 More niches that can pass (2026-10-25, branch `sourcing-and-q6`)

Week 43's live run (issue #8) found no PASS or REVIEW candidate. These changes follow your decisions on that result.

- **Q6 decided: removable personal data is allowed.** `allow_removable_personal_data` is now `true`, and such candidates can PASS or be REVIEW. Examples are a recruiter's name inside a job post, or author fields in package metadata.
  - The build brief tells the Builder to leave those fields out and add them to `EXTRA_FORBIDDEN_KEYS`.
  - Core personal data and logins still always fail.
  - On the sample data, PyPI and WordPress now pass. On week 43's data, Greenhouse would have been 🔎 REVIEW.
- **Platform exclusions (Q18):** `scout.exclude.platforms` leaves out Google, Amazon, ChatGPT, Perplexity, Copilot, G2, Indeed, Glassdoor and other platforms whose terms forbid scraping, that need a login, or that disallow search pages in robots.txt.
- **Memory of hard failures (Q18):** niches that failed Legality for a login, core personal data, terms that forbid the use, or robots.txt are skipped for 12 weeks (`scout.history.skip_hard_fails_weeks`).
  - Each Validator brief carries the list as hidden JSON, and Scout reads it back from the weekly issues.
  - The brief says how many niches were added that week, and the issue's Data line says how many were skipped.
- **Tests:** 235 pass. New tests cover the memory, the platform list, the Q6 switch and the Builder's personal-data instruction.

## 🧪 Real fixtures for Builder builds (2026-10-25, branch `builder-fixtures`)

- **Why:** in the Builder rehearsal (issue #5, PR #6) Claude could not save raw API responses. 6 of its commands were blocked, and it rebuilt the fixture from WebFetch's summary instead.
- **Fetch helper (`templates/python-actor/tests/fetch_fixture.py`):** `python -m tests.fetch_fixture <url> tests/fixtures/<name>` saves one real response. It goes through the Actor's own polite client and robots.txt check, then the privacy guard. It writes only under `tests/fixtures/`, and runs under the `python` permission Claude already has, so it does not add `curl`, which would skip robots.txt. 5 new template tests (30 in all).
- **`docs/BUILDER.md`:** tells Claude to use the helper and not to build fixtures from WebFetch.
- **`claude.yml`:** keeps Claude's full transcript as the `builder-transcript` artifact for 14 days, so blocked commands and costs can be read after a build.
- **Rehearsal result:** one build took about 5½ minutes, 40 turns and $1.05. The PR passed the test, actors and scope checks.

## 🔎 REVIEW verdict for unclear terms (2026-10-25, branch `phase-2-review`)

- **What it is:** a candidate that passes every other rule, but whose terms neither forbid nor clearly allow reuse, is marked 🔎 REVIEW (QUESTIONS Q17). The rules: official API or public feed, no login, no personal data, robots.txt allowing it.
- **In the brief:** REVIEW candidates get their own section with the terms passage and a ready-to-paste command. They rank right after passing candidates in the issue.
- **In the Builder:** a REVIEW candidate builds only with `/build <niche-id> terms-reviewed`. The flag cannot rescue a failing candidate. The brief tells Claude not to claim in the README that the terms explicitly allow the use.
- **On the 2026-10-24 rehearsal data:** Greenhouse Jobs API and Sitemap Extractor become REVIEW. Everything else is unchanged.
- **Brief note:** its closing note now explains the `go` + `/build` flow (the Builder exists since Phase 2).

## Phase 2, part 1: Builder and Publisher infrastructure (2026-10-25, branch `phase-2`)

Everything that does not depend on which niche passes. The first three Actors wait for Scout candidates that pass all five checks.

### Added

- **Actor template (`templates/python-actor/`)**, based on Apify's official `python-start` template (Dockerfile, `.actor/` schemas, `my_actor` package), with the factory's rules built in:
  - **`polite.py`:** a per-host rate limit, and retries with exponential back-off that honour `Retry-After`.
  - **`robots.py`:** RFC 9309 matching. When a site's robots.txt cannot be read, the whole site is skipped.
  - **`privacy.py`:** every item passes through a guard that drops personal-data fields and blanks e-mail addresses and international phone numbers.
  - **`main.py`:** charges per result with Apify's synthetic `apify-default-dataset-item` event, and stops at the user's spending limit.
  - **`source.py`:** the only niche-specific file.
  - **Listing and docs:** a Store README skeleton, plus `.actor/pricing.json` and `.actor/listing.json` for the Publisher.
  - **Tests:** 25 tests, including local runs that charge against a test pricing setup.
- **Builder (`.github/workflows/claude.yml`, `factory/builder/`, `docs/BUILDER.md`):**
  - **Trigger:** `go` plus `/build <niche-id>`, from the owner only (Q1).
  - **Preparation:** code refuses the build unless the niche passed all five checks. It writes a build brief, copies the template to `actors/<name>/` on a `build/<name>` branch, and runs the Claude Code GitHub Action with `claude-opus-5-5`.
  - **Claude's tools:** limited to editing files, running Python, tests and schema validation, committing, pushing that branch, opening the PR and commenting. It is denied `gh pr merge`, force-pushes and `apify push`.
- **Publisher (`.github/workflows/publish.yml`, `factory/publisher/`):** after a merge to `main` touching `actors/`, it tests each changed Actor, deploys it with `apify push`, and, for an Actor that is not public yet, opens the issue "Publish <name>" with the listing text and the monetization values (Q14).
- **Tests workflow:** now also tests the template and every Actor in its own environment, runs `apify validate-schema` on each, and checks that a `build/*` pull request changes only one `actors/<name>/` folder.
- **Factory tests:** for the Builder's preparation and its refusals, the scope check, the listing generator, and guards on the template and the Builder workflow.

### Fixed while building

- In the Actor template, a run without pay-per-event pricing (a free Actor, or before monetization is set up) would have stopped after the first result. The SDK reports "limit reached" on every push in that case, so the template now acts on charge results only under pay-per-event pricing.
- The personal-data guard now normalises keys like `profileURL` correctly.

### Needs you (Q15)

- Install the Claude GitHub App on the repository.
- Recommended: add branch protection on `main`.

## Phase 1 fixes after the first live run (2026-10-24, branch `phase-1-live-fixes`)

The first run against live data (Scout and the Validator, both as dry runs, from the owner's machine) worked end to end: 9,688 Store Actors from 19 queries, 245 Actor detail lookups, 148 ideas, and 20 Claude assessments in about 2.5 minutes for roughly $0.15. It found two problems, fixed here:

- **Ideas:** the Ideas page loads its list in the browser, so none were parsed. Scout now reads the page's own export (`/api/ideas/download?format=json&status=toDevelop`) and takes each idea's upvotes from its page (QUESTIONS Q4). New config: `apify.ideas_export_url`, `scout.ideas.max_pages`. Only `open_to_develop` counts as open.
- **Niche grouping:** real titles carry sales text after a separator ("Tweet Scraper V2 - X Scraper / Twitter Scraper…"). Keywords now come from the part before the first separator, pure numbers are ignored and `com` is a stopword. The same Store data grouped into 3,955 niches instead of 5,111.
- `owner.apify_username` is set to `guayox` (Q7).
- Fixtures: a synthetic Ideas export and idea pages replace the guessed `ideas.html`, plus small real samples of the export and an idea page. A Booking.com sample assessment was added because the new grouping brings that niche into the sample top 20.
- The `APIFY_TOKEN` and `ANTHROPIC_API_KEY` GitHub Actions secrets are set.
- **Shortlist (QUESTIONS Q13):** on live data no candidate passed, because the top 20 by demand were social-media and lead-list scrapers and generic tools. Scout now leaves out niches that can never pass (`scout.exclude`: title words and Store categories), shortlists 40 (`scout.candidates_to_validate`), and the Validator assesses all 40 and rewrites the issue with the best 20 after validation, passing candidates first. `scout.details.niche_pool` rises from 40 to 50. On the 2026-10-24 data, 1,805 of 3,955 niches were left out and the shortlist became G2 reviews, Flashscore and Sofascore, Yandex search, SEO tools, Greenhouse jobs, sitemaps and retail products, among others.
- **Terms research (QUESTIONS Q9):** a dry run of the workflow on GitHub still gave 0 of 20 passing, and every near-miss failed only on "terms unclear". The Validator now gives Claude web search and web fetch (`validator.research`). It must cite the terms page and quote the deciding sentence, and code accepts "terms allow it" only with both. The brief shows the quote and link for passing candidates. Assessments run 4 at a time (`validator.concurrency`), long tool turns are resumed when the API pauses them, and the Scout workflow timeout rises to 75 minutes.

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
