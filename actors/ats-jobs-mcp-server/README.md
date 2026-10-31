# Job Search MCP Server: match CVs to open jobs, salaries and hiring data for AI agents

Give Claude, Cursor or any MCP client live access to company job boards. Ask "what engineering roles is Notion
hiring for?" or "here is my CV: which of these companies have a job for me?" and the agent finds which applicant
tracking system (ATS) each company uses, then reads its open jobs from **Greenhouse**, **Lever**, **Ashby**,
**Workable** or **Personio**, with **salary ranges** where the company publishes them.

## What can the Job Search MCP Server do?

- **Find a company's job board (ATS lookup):** give a company name and it tries the five platforms for you (for
  example "notion" is on Ashby, "airbnb" on Greenhouse) and says how many jobs are open. Free: nothing is charged.
- **Search open jobs:** one or more companies (names or job board URLs), with optional title and location
  keywords. Each job comes with title, company, location, department, workplace and employment type, salary range,
  posting date and the link to apply.
- **Match skills or a CV to jobs:** pass skills (your agent can read them from a CV) and only jobs whose title or
  description mentions them come back, best matches first, each with the skills it matched.
- **Short or full answers:** a compact summary per job by default, or the description too (first 1,500
  characters), so answers stay within your agent's context.
- **Polite and clean:** it reads only each platform's public job feed, respects robots.txt and rate limits, and
  returns no personal data (e-mail addresses and phone numbers in descriptions are replaced with `[removed]`).

## What can you use the Job Search MCP Server for?

| Who | Use case | Ask your agent, for example |
|---|---|---|
| Job seekers | **Match your CV to open jobs** at the companies you want to work for | "Here is my CV. Which open jobs at Notion, Ramp and Airbnb fit my skills?" |
| Job seekers | **Check whether a company is hiring**, including remote roles | "Is Warp hiring remote engineers?" |
| Job seekers, recruiters, HR | **Salary research and benchmarking** from published pay ranges | "What do Airbnb and Ramp pay account executives?" |
| Recruiters, talent teams | **Competitor hiring intelligence:** which roles rivals open, in which teams and places | "Which sales roles have our three competitors opened, and where?" |
| Sales and growth teams | **Hiring signals as buying intent:** companies hiring for what you sell to | "Which of these 20 accounts are hiring data engineers?" |
| Sales, HR tech vendors | **Tech stack from job posts:** which tools a company asks candidates to know | "Do any of these companies mention Snowflake or dbt in their job descriptions?" |
| Recruiters, HR tech vendors | **ATS lookup:** which applicant tracking system a company uses (free) | "Which ATS does Notion use?" |
| Investors, analysts | **Hiring momentum:** open roles per company and department | "How many open jobs does each of these companies have, by department?" |
| HR teams, hiring managers | **Job description research:** how peers word the same role | "Show me how Airbnb and Ramp describe a product designer role." |
| Agent builders | **Live job data for your own agent**, career assistant or job bot over MCP | Connect the server and call `search_jobs` from your agent |

**What it does not do:** it does not discover companies for you (your agent names them, up to 20 per call), and it
covers only these five ATS platforms, not Workday, iCIMS, SmartRecruiters or job boards like LinkedIn and Indeed.
Salaries appear only where the company publishes them. For scheduled tracking and bulk exports, use the
[Career Site Jobs Scraper](https://apify.com/guayox/greenhouse-jobs-scraper).

## Tools

| Tool | Arguments | Returns | Charged |
|---|---|---|---|
| `find_job_board` | `company` | the board (for example `ashby:notion`), its platform and the number of open jobs | No |
| `search_jobs` | `companies`, `title_keywords`, `location_keywords`, `skills`, `max_results` (default 25, at most 100), `include_descriptions` | the jobs found (with `matched_skills` when skills are given) and the board used for each company | Per job returned |

## How to connect the Job Search MCP Server to Claude, Cursor or another MCP client

The server runs in Apify's Standby mode: it starts when your agent calls it and stops when idle. Its MCP endpoint
is shown on the Actor's page in Apify Console, and has this form:

```
https://<your-apify-username>--ats-jobs-mcp-server.apify.actor/mcp
```

Authenticate with your [Apify API token](https://console.apify.com/settings/integrations) as a Bearer token.

**Claude Code:**

```bash
claude mcp add --transport http ats-jobs https://<your-apify-username>--ats-jobs-mcp-server.apify.actor/mcp \
  --header "Authorization: Bearer <your-apify-token>"
```

**Any MCP client** that supports Streamable HTTP: use the URL above with the header
`Authorization: Bearer <your-apify-token>`.

You can also run the Actor normally from Apify Console or the API. A normal run reads the job boards in its input
(for example `["airbnb", "lever:zoox", "ashby:warp"]`) and writes every open job to its dataset.

## How much does the Job Search MCP Server cost?

You pay per job returned: $1.60 per 1,000 jobs, the same as a normal run. `find_job_board` is free. While the
server runs in Standby mode you also pay Apify's platform usage for the run, as for every Standby Actor; it stops
after a short idle time. Set a maximum cost per run, and `search_jobs` stops when it is reached.

## Example

Ask your agent: *"Is Warp hiring account executives, and what do they pay?"* The agent calls:

```json
{"tool": "search_jobs", "arguments": {"companies": ["warp"], "title_keywords": ["account"], "max_results": 10}}
```

and gets back, for each job (here a real answer):

```json
{
    "title": "Account Executive",
    "company": null,
    "location": "New York",
    "department": "Sales",
    "workplace_type": "onsite",
    "employment_type": "Full-time",
    "salary_min": 160000,
    "salary_max": 200000,
    "salary_currency": "USD",
    "salary_interval": "per-year-salary",
    "absolute_url": "https://jobs.ashbyhq.com/warp/6fa4373f-2f5e-4fa3-9ce5-e662275ebba8",
    "first_published": null,
    "updated_at": "2025-12-04T18:43:07.001+00:00",
    "platform": "ashby",
    "board_token": "warp",
    "job_id": "6fa4373f-2f5e-4fa3-9ce5-e662275ebba8"
}
```

## How to match your CV to open jobs with AI

Give your agent your CV and the companies you are interested in, and ask: *"Here is my CV. Which open jobs at
Warp and Zoox fit me best?"* The agent reads the skills from your CV and calls:

```json
{"tool": "search_jobs", "arguments": {"companies": ["warp", "zoox"], "skills": ["Salesforce", "LLM", "outbound", "B2B SaaS"]}}
```

Only jobs that mention at least one skill come back, the ones that mention the most first, each with a
`matched_skills` list such as `["Salesforce", "LLM", "outbound"]`. Skills match as whole words and not
case-sensitively ("Go" does not match "good", "C" does not match "C++"). Your CV stays with your agent: the server
receives only the skill words, and stores nothing about you. Only the jobs returned are charged.

## Related Actors

- [Career Site Jobs Scraper](https://apify.com/guayox/greenhouse-jobs-scraper): the same five job boards for bulk exports to JSON, CSV or Excel, and daily
  feeds of only new jobs on a schedule.

## FAQ

**Is it legal to use this data?** The server reads only the platforms' public job feeds, the same jobs each company
shows on its public careers page:

- **Greenhouse:** the [Job Board API](https://docs.greenhouse.io/job-board.html). Greenhouse's documentation says
  this data is publicly available and its GET endpoints need no authentication.
- **Lever:** the [Postings API](https://github.com/lever/postings-api). Lever's documentation says published
  postings "are publicly viewable" and "may be scraped by third parties".
- **Ashby:** the [Public Job Posting API](https://developers.ashbyhq.com/docs/public-job-posting-api). A salary is
  returned only when the company shows pay on its posting.
- **Workable:** the public jobs endpoint described in Workable's help centre
  ([Using the Workable API to create a careers page](https://help.workable.com/hc/en-us/articles/115012771647)).
- **Personio:** the XML job feed in Personio's
  [developer documentation](https://developer.personio.de/docs/retrieving-open-job-positions).

Ashby's, Workable's and Personio's documentation does not address third-party use either way. The server needs no
login, checks robots.txt before each request, keeps to a polite request rate, and returns no personal data. Check
that your own use of the job postings suits your purpose and jurisdiction.

**A company was not found.** It may not use one of these five platforms, or its board has a different name. Ask
the agent to use the job board URL from the company's careers page instead (for example
`https://jobs.lever.co/<company>`).

**Why is `company` sometimes empty?** Lever's and Ashby's feeds do not include the company's display name; every
job carries its `board_token`, which identifies the company.

**Something is not working.** Open an issue on the Actor's **Issues** tab; it is monitored daily.
