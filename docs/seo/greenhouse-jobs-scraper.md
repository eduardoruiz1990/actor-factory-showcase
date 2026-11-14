# SEO tracking: Greenhouse, Lever, Ashby & Workable Jobs Scraper (`guayox/greenhouse-jobs-scraper`)

What the listing targets and how it ranks in Apify Store search. Update the results table at each review.

## Listing (from 2026-11-14, branch `ccr-5f92142f-5egvif`)

- **Title:** Greenhouse, Lever, Ashby & Workable Jobs Scraper
- **SEO title:** Greenhouse, Lever & Ashby Jobs API: ATS career site jobs
- **SEO description:** Jobs from Greenhouse, Lever, Ashby, Workable and Personio career sites, live from each ATS:
  salaries, locations, descriptions. $0.99 per 1,000 jobs.
- **Categories:** Jobs, Automation

Before (2026-10-31 to 2026-11-14): title "Career Site Jobs Scraper: Greenhouse, Lever, Ashby & More", SEO title "Career Site
Jobs API: Greenhouse, Lever, Ashby, Workable". The "career site" phrase is held by
`fantastic-jobs/career-site-job-listing-api` (1,578 monthly users).

## Results

Store search positions come from `GET /v2/store?search=<phrase>&limit=1000` (the API returns at most about 800–900
results per query, so "—" means outside them). Users come from the Store listing; "outside runs" from
`publicActorRunStats30Days`, which leaves out the owner's runs but includes Apify's daily automated test.

| Date | Users 30d | Outside runs 30d | "greenhouse jobs" | "greenhouse" | "lever jobs" | "ashby jobs" | "ats jobs" | "career site jobs" | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-14 | 2 (owner + 1) | 20, all succeeded | #372 | #142 | — | — | — | #34 | Baseline, before the retitle. The 20 outside runs, about one a day, look like Apify's daily test. No reviews or bookmarks. |
| 2026-12-01 | | | | | | | | | Two weeks after the retitle |
| 2027-01-03 | | | | | | | | | Q29 stop-rule checkpoint |
