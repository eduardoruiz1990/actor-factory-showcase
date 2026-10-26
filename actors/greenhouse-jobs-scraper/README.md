# Greenhouse & Lever Jobs Scraper: every open job, with salary ranges

Get every open job from any company that hires through **Greenhouse** or **Lever**, two of the most widely used
applicant tracking systems (ATS). You get the job title, location, department, office, job URL, posting date, the full
job description and, where the company publishes it, the **salary range**, as clean JSON, CSV or Excel. Give it board
tokens (such as `airbnb` or `lever:zoox`) or job board URLs, and it reads them from each platform's official public
job board API. Recruiters, job boards, job aggregators, HR-tech teams and market researchers use it to track who is
hiring, for which roles, where and for how much.

## What can this Actor do?

- Get every open job from any company's Greenhouse or Lever board, with one API request per company
- Mix both platforms in one run, with the same output fields for every job
- Accept board tokens or URLs: `airbnb`, `https://boards.greenhouse.io/airbnb`,
  `https://job-boards.greenhouse.io/airbnb/jobs/123`, `lever:zoox`, `https://jobs.lever.co/zoox`, and EU-hosted Lever
  boards (`lever-eu:<company>` or `https://jobs.eu.lever.co/<company>`)
- Return salary ranges (minimum, maximum, currency, interval), employment type and workplace type from Lever boards
- Return the full description as HTML and as plain text, with every department and office
- Filter by title keywords (for example "engineer", "data") and location keywords (for example "Remote", "London")
- Turn descriptions off for a fast, light list of titles, locations and links
- Skip unknown boards and bad responses with a clear log message, and carry on with the rest
- Polite by design: it respects robots.txt and rate limits, and retries with back-off
- No personal data: names, e-mail addresses and phone numbers are never stored
- Export to JSON, CSV, Excel or HTML, or connect through the Apify API, integrations and MCP

## What data do you get?

One result per open job. Every job has the same fields; a field a platform does not publish is `null`.

| Field | Description |
|---|---|
| `platform` | `greenhouse` or `lever` |
| `board_token` | The board the job came from, for example `airbnb` or `zoox` |
| `company` | Company name as shown on a Greenhouse board (Lever's API does not publish it; use `board_token`) |
| `job_id` | The platform's job ID: a number on Greenhouse, an ID string on Lever (stable across runs) |
| `internal_job_id` | Greenhouse internal job ID, shared by posts of the same job |
| `requisition_id` | The company's own requisition ID, when it sets one (Greenhouse) |
| `title` | Job title |
| `location` | Location text of the posting, for example `Tokyo, Japan` or `Remote - US` |
| `department` | First department or team of the job |
| `departments` | All departments (Greenhouse), or the department and team (Lever) |
| `office` | First office of the job |
| `offices` | All offices or locations of the job |
| `absolute_url` | Link to the job posting where candidates apply |
| `language` | Language code of the posting, for example `en` (Greenhouse) |
| `updated_at` | When the posting was last updated (Greenhouse, ISO 8601 with time zone) |
| `first_published` | When the posting was first published (ISO 8601 with time zone) |
| `content` | Full job description as HTML |
| `content_text` | Full job description as plain text, one paragraph or bullet per line |
| `employment_type` | For example `Full-time` or `Permanent` (Lever) |
| `workplace_type` | `onsite`, `hybrid` or `remote` (Lever) |
| `salary_min`, `salary_max` | Salary range, when the company publishes one (Lever) |
| `salary_currency` | For example `USD` (Lever) |
| `salary_interval` | For example `per-year-salary` (Lever) |
| `fetched_at` | When the Actor read the job (UTC) |

With **Include full job descriptions** off, `content` and `content_text` are empty (and, on Greenhouse, the
departments and offices too). The Actor does not return the companies' custom application questions or custom
metadata fields. E-mail addresses and phone numbers that appear in a description are replaced with `[removed]`.

## How much does it cost?

You pay per result: $1.60 per 1,000 jobs, plus a small fee per run that Apify sets. A run of 1,000 jobs costs about
$1.60, whichever platform they come from. Set a maximum cost per run and the Actor stops when it is reached. Use
**Maximum results** and the keyword filters to pay only for the jobs you need; jobs removed by a filter are not charged.

## How to use it

1. Click **Try for free**.
2. Enter one or more job boards: a Greenhouse board token or URL, or a Lever board as `lever:<company>` or its
   `jobs.lever.co` URL.
3. Click **Start** and download the results when the run finishes.

## Input

- **Job boards** (`boardTokens`, required): the companies to read, on Greenhouse or Lever.
- **Include full job descriptions** (`includeContent`, default `true`): descriptions, plus departments and offices
  on Greenhouse.
- **Title keywords** (`titleKeywords`): keep jobs whose title contains any of these words.
- **Location keywords** (`locationKeywords`): keep jobs whose location or office contains any of these words.
- **Maximum results** (`maxResults`, default 1,000): stop after this many jobs.
- **Maximum requests per second** (`maxRequestsPerSecond`, default and maximum 1): polite rate limit.

```json
{
    "boardTokens": ["airbnb", "https://job-boards.greenhouse.io/stripe", "lever:zoox", "https://jobs.lever.co/palantir"],
    "includeContent": true,
    "titleKeywords": ["engineer", "counsel"],
    "locationKeywords": ["California", "Remote"],
    "maxResults": 500
}
```

## Output example

A Lever job with a salary range:

```json
{
    "platform": "lever",
    "board_token": "zoox",
    "company": null,
    "job_id": "e8a190f0-7a89-4c11-a6a0-452ff6234749",
    "internal_job_id": null,
    "requisition_id": null,
    "title": "Administrative Business Partner, Floater",
    "location": "Foster City, CA",
    "department": "Executive Office",
    "departments": ["Executive Office"],
    "office": "Foster City, CA",
    "offices": ["Foster City, CA"],
    "absolute_url": "https://jobs.lever.co/zoox/e8a190f0-7a89-4c11-a6a0-452ff6234749",
    "language": null,
    "updated_at": null,
    "first_published": "2026-10-06T17:27:44+00:00",
    "content": "<div><span style=\"font-size: 12pt;\">Zoox is building the future of transportation. ...",
    "content_text": "Zoox is building the future of transportation. To do that, we’re also building an incredible crew ...",
    "employment_type": "Full-time",
    "workplace_type": "hybrid",
    "salary_min": 123000,
    "salary_max": 168000,
    "salary_currency": "USD",
    "salary_interval": "per-year-salary",
    "fetched_at": "2026-10-26T18:07:24+00:00"
}
```

A Greenhouse job:

```json
{
    "platform": "greenhouse",
    "board_token": "airbnb",
    "company": "Airbnb",
    "job_id": 7789554,
    "internal_job_id": 3407102,
    "requisition_id": "ONE",
    "title": "Associate Legal Counsel, Japan",
    "location": "Tokyo, Japan",
    "department": "Legal",
    "departments": ["Legal"],
    "office": "Tokyo, Japan",
    "offices": ["Tokyo, Japan"],
    "absolute_url": "https://careers.airbnb.com/positions/7789554?gh_jid=7789554",
    "language": "en",
    "updated_at": "2026-09-29T20:00:54-04:00",
    "first_published": "2026-04-13T04:49:05-04:00",
    "content": "<div class=\"content-intro\"><p><span style=\"...\">Airbnb was born in 2007 when two hosts welcomed three guests ...",
    "content_text": "Airbnb was born in 2007 when two hosts welcomed three guests to their San Francisco home, ...",
    "employment_type": null,
    "workplace_type": null,
    "salary_min": null,
    "salary_max": null,
    "salary_currency": null,
    "salary_interval": null,
    "fetched_at": "2026-10-25T09:48:00+00:00"
}
```

## Use it through the API or AI agents

Call the Actor from your code with the [Apify API](https://docs.apify.com/api/v2), or from an AI agent through
[Apify's MCP server](https://mcp.apify.com). A typical automated use is a daily scheduled run over a list of
companies on both platforms that feeds new `job_id`s into a job board, a CRM, a salary benchmark or a hiring-signals
dashboard.

## FAQ

**Is it legal to use this data?** The Actor reads only the platforms' public job board APIs, the same data shown on
each company's public job board:

- **Greenhouse:** the [Job Board API](https://docs.greenhouse.io/job-board.html) (`boards-api.greenhouse.io`).
  Greenhouse's documentation says this data is publicly available and its GET endpoints need no authentication.
  Greenhouse's legal terms are at [greenhouse.com/legal](https://www.greenhouse.com/legal); they do not publish
  separate terms for the Job Board API.
- **Lever:** the [Postings API](https://github.com/lever/postings-api) (`api.lever.co`). Lever's documentation says
  published postings "are publicly viewable" and "may be scraped by third parties". Its robots.txt allows crawling
  with a 1-second delay, which the Actor keeps to.

The Actor only reads open job postings, needs no login, checks each API's robots.txt before each request, keeps to a
polite request rate, and stores no personal data. Check that your own use of the job postings suits your purpose and
jurisdiction.

**Where do I find a company's board?** Open the company's careers page and click a job.

- If the link goes to `boards.greenhouse.io/<token>/...` or `job-boards.greenhouse.io/<token>/...`, paste the URL or
  the `<token>`. Some companies show Greenhouse jobs on their own site with a `gh_jid=` link; their token is usually
  the company name.
- If it goes to `jobs.lever.co/<company>/...`, paste the URL or enter `lever:<company>`.

**A board returned no jobs.** Either the company has no open jobs or the token is wrong; the run log says
"No Greenhouse board called ..." or "No Lever board called ..." for an unknown board. Only companies that use
Greenhouse or Lever are covered.

**Why is `company` empty for Lever jobs?** Lever's public API does not include the company's display name. Every job
carries its `board_token` (for example `zoox`), which identifies the company.

**How fresh is the data?** Every run fetches it live from the source.

**Something is not working.** Open an issue on the Actor's **Issues** tab; it is monitored daily.
