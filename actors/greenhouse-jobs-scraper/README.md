# Greenhouse Jobs Scraper: every open job from any Greenhouse job board

Get every open job from any company that hires through Greenhouse. You get the job title, location, department,
office, job URL, posting dates and the full job description, as clean JSON, CSV or Excel. Give it one or more
Greenhouse board tokens (such as `airbnb`) or job board URLs, and it reads them from Greenhouse's official public
Job Board API. Recruiters, job boards, job aggregators, HR-tech teams and market researchers use it to track who is
hiring, for which roles and where.

## What can this Actor do?

- Get every open job from any company's Greenhouse board, with one API request per company
- Accept board tokens (`airbnb`) or any board URL (`https://boards.greenhouse.io/airbnb`,
  `https://job-boards.greenhouse.io/airbnb/jobs/123`, `https://boards.greenhouse.io/embed/job_board?for=airbnb`)
- Return the full description as HTML and as plain text, with every department and office
- Filter by title keywords (for example "engineer", "data") and location keywords (for example "Remote", "London")
- Turn descriptions off for a fast, light list of titles, locations and links
- Skip unknown boards and bad responses with a clear log message, and carry on with the rest
- Polite by design: it respects robots.txt and rate limits, and retries with back-off
- No personal data: names, e-mail addresses and phone numbers are never stored
- Export to JSON, CSV, Excel or HTML, or connect through the Apify API, integrations and MCP

## What data do you get?

One result per open job:

| Field | Description |
|---|---|
| `board_token` | The Greenhouse board token the job came from, for example `airbnb` |
| `company` | Company name as shown on the board |
| `job_id` | Greenhouse job ID (stable across runs, good for de-duplication) |
| `internal_job_id` | Greenhouse internal job ID, shared by posts of the same job |
| `requisition_id` | The company's own requisition ID, when it sets one |
| `title` | Job title |
| `location` | Location text of the posting, for example `Tokyo, Japan` or `Remote - US` |
| `department` | First department of the job |
| `departments` | All departments of the job |
| `office` | First office of the job |
| `offices` | All offices of the job |
| `absolute_url` | Link to the job posting where candidates apply |
| `language` | Language code of the posting, for example `en` |
| `updated_at` | When the posting was last updated (ISO 8601, with time zone) |
| `first_published` | When the posting was first published (ISO 8601, with time zone) |
| `content` | Full job description as HTML |
| `content_text` | Full job description as plain text, one paragraph or bullet per line |
| `fetched_at` | When the Actor read the job (UTC) |

With **Include full job descriptions** off, `content`, `content_text`, `department(s)` and `office(s)` are empty.
The Actor does not return the companies' custom application questions or custom metadata fields. E-mail addresses
and phone numbers that appear in a description are replaced with `[removed]`.

## How much does it cost?

You pay per result: $1.60 per 1,000 jobs, plus a small fee per run that Apify sets. A run of 1,000 jobs costs about
$1.60. Set a maximum cost per run and the Actor stops when it is reached. Use **Maximum results** and the keyword
filters to pay only for the jobs you need; jobs removed by a filter are not charged.

## How to use it

1. Click **Try for free**.
2. Enter one or more Greenhouse board tokens or board URLs. The token is the part of the company's job board URL
   after `boards.greenhouse.io/` or `job-boards.greenhouse.io/`.
3. Click **Start** and download the results when the run finishes.

## Input

- **Greenhouse board tokens or URLs** (`boardTokens`, required): the companies to read.
- **Include full job descriptions** (`includeContent`, default `true`): descriptions, departments and offices.
- **Title keywords** (`titleKeywords`): keep jobs whose title contains any of these words.
- **Location keywords** (`locationKeywords`): keep jobs whose location or office contains any of these words.
- **Maximum results** (`maxResults`, default 1,000): stop after this many jobs.
- **Maximum requests per second** (`maxRequestsPerSecond`, default 1): polite rate limit.

```json
{
    "boardTokens": ["airbnb", "https://job-boards.greenhouse.io/stripe"],
    "includeContent": true,
    "titleKeywords": ["engineer", "counsel"],
    "locationKeywords": ["Japan", "Remote"],
    "maxResults": 500
}
```

## Output example

```json
{
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
    "content": "<div class=\"content-intro\"><p><span style=\"...\">Airbnb was born in 2007 when two hosts welcomed three guests ...</span></p></div> ...",
    "content_text": "Airbnb was born in 2007 when two hosts welcomed three guests to their San Francisco home, ...\nThe Community You Will Join:\n...",
    "fetched_at": "2026-10-25T09:48:00+00:00"
}
```

## Use it through the API or AI agents

Call the Actor from your code with the [Apify API](https://docs.apify.com/api/v2), or from an AI agent through
[Apify's MCP server](https://mcp.apify.com). A typical automated use is a daily scheduled run over a list of
companies that feeds new `job_id`s into a job board, a CRM or a hiring-signals dashboard.

## FAQ

**Is it legal to use this data?** The Actor reads Greenhouse's public
[Job Board API](https://docs.greenhouse.io/job-board.html) (`boards-api.greenhouse.io`), the same data shown on each
company's public job board. Greenhouse's documentation says this data is publicly available and its GET endpoints
need no authentication. Greenhouse's legal terms are at [greenhouse.com/legal](https://www.greenhouse.com/legal);
they do not publish separate terms for the Job Board API. The Actor only reads open job postings, needs no login,
checks the API's robots.txt before each request, keeps to a polite request rate, and stores no personal data.
Check that your own use of the job postings suits your purpose and jurisdiction.

**Where do I find a company's board token?** Open the company's careers page and click a job. If the link goes to
`boards.greenhouse.io/<token>/...` or `job-boards.greenhouse.io/<token>/...`, that `<token>` is it; you can also
paste the whole URL. Some companies show Greenhouse jobs on their own site with a `gh_jid=` link; their token is
usually the company name.

**A board returned no jobs.** Either the company has no open jobs or the token is wrong; the run log says
"No Greenhouse board called ..." for an unknown token. Only companies that use Greenhouse are covered.

**How fresh is the data?** Every run fetches it live from the source.

**Something is not working.** Open an issue on the Actor's **Issues** tab; it is monitored daily.
