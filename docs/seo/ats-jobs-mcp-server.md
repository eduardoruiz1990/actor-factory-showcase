# SEO tracking: Job Search MCP Server (`guayox/ats-jobs-mcp-server`)

What the listing targets, where each phrase appears, and how it is doing. Update the results table at each review.

## Listing (from 2026-10-31, branch `mcp-skills-use-cases`)

- **Title:** Job Search MCP Server: Greenhouse, Lever, Ashby & More
- **SEO title:** Job Search MCP Server: CV matching, salaries, hiring data
- **SEO description:** MCP server for Claude, Cursor & AI agents: match a CV to open jobs, compare salaries, track
  competitor hiring on Greenhouse, Lever, Ashby & more.
- **Categories:** Agents, Jobs

Before: "ATS Jobs MCP Server: Greenhouse, Lever, Ashby & More", SEO title "ATS Jobs MCP Server: open jobs and salaries for
AI agents". "ATS" is not what buyers search for; "job search MCP server" is how MCP directories name this kind of
server.

## Target phrases by use case

| Use case | Who | Target phrases | Where they appear |
|---|---|---|---|
| Match a CV to open jobs | Job seekers, career assistants | resume job matching, match CV to jobs, find jobs matching my resume | SEO title and description, README heading "How to match your CV to open jobs with AI", `skills` argument |
| Search without naming companies | Job seekers, agent builders | remote [role] jobs, job search without company names, search jobs across companies | Description, README heading "How to search jobs without naming companies", use-case table |
| MCP access to jobs | Agent builders | job search MCP server, jobs MCP, jobs API for AI agents | Title, SEO title, README H1 |
| Is a company hiring | Job seekers | is [company] hiring, remote jobs at [company] | README use-case table |
| Salary research | Job seekers, recruiters, HR | salary data API, salary benchmarking, pay ranges | SEO title ("salaries"), use-case table |
| Competitor hiring | Recruiters, talent teams | competitor hiring tracker, competitor job postings | SEO description, use-case table |
| Hiring signals | Sales and growth teams | hiring signals, buying intent data | SEO title ("hiring data"), use-case table |
| Tech stack from job posts | Sales, HR tech vendors | technographics from job postings | Use-case table |
| ATS lookup | Recruiters, HR tech vendors | what ATS does a company use, ATS lookup | Description, "What can it do?" list |
| Hiring momentum | Investors, analysts | hiring trends data, open roles by department | Use-case table |
| Job description research | HR teams | job description examples | Use-case table |

Excluded on purpose: LinkedIn, Indeed, Workday (not covered; claiming them would mislead buyers and hurt the
quality score's congruency).

## Results

Read from the public Store page and Apify Console → the Actor → **Insights** (users, runs, Store page views where
shown). Google: search each "Target phrases" entry and note whether the Actor's page shows on the first page.

| Date | Total users | Monthly active users | Success rate | Store search "job search mcp" | Notes |
|---|---|---|---|---|---|
| 2026-10-31 | 1 | 0 | 0.0% (no user runs yet) | not checked | Baseline, before this listing. The only run, the owner's, succeeded; Apify's daily test skips Standby Actors, so the Store rate and the quality score's health warning had no runs to measure. Quality score 68; the jobs Actor had 82, 2 users, 1 monthly. |
| 2026-11-14 | | | | | Two weeks after the listing change |
| 2026-12-01 | | | | | |
| 2027-01-03 | | | | | January checkpoint |
