# Career Site Jobs Scraper: every open job straight from company career sites, with salary ranges

Get every open job straight from company career sites: the Career Site Jobs Scraper reads any company that hires
through **Greenhouse**, **Lever**, **Ashby**, **Workable** or **Personio**, five of the most widely used applicant
tracking systems (ATS): US and European tech companies, scale-ups
and thousands of small and mid-sized businesses. You get the job title, company, location, department, office, job
URL, posting date, the full job description and, where the company publishes it, the **salary range**, as clean JSON,
CSV or Excel. Give it board names (such as `airbnb`, `lever:zoox`, `ashby:ramp`, `workable:blueground` or
`personio:tado`) or job board URLs, and it reads each platform's public job feed. Recruiters, job boards, job aggregators, HR-tech teams and market researchers use it to track who is
hiring, for which roles, where and for how much.

## What can this Actor do?

- Get every open job from any company's Greenhouse, Lever, Ashby, Workable or Personio board, with one request per
  company
- Mix the five platforms in one run, with the same output fields for every job
- Accept board names or the URLs you copy from a careers page (see the table below)
- Return salary ranges (minimum, maximum, currency, interval) from Greenhouse, Lever, Ashby and Personio, wherever the
  company publishes pay ranges, plus employment type and workplace type
- Return the full description as HTML and as plain text, with every department and office
- Filter by title keywords (for example "engineer", "data") and location keywords (for example "Remote", "London")
- Turn descriptions off for a fast, light list of titles, locations and links
- **Get only new jobs:** schedule it daily with **Only new jobs** on, and each run returns and charges only jobs posted since the last run
- Skip unknown boards and bad responses with a clear log message, and carry on with the rest
- Polite by design: it respects robots.txt and rate limits, and retries with back-off
- No personal data: names, e-mail addresses and phone numbers are never stored
- Export to JSON, CSV, Excel or HTML, or connect through the Apify API, integrations and MCP

## Jobs straight from company career pages

Every job comes from the company's own career site, read live from its ATS at run time: no job-board reposts, no
stale database, no expired or "ghost" jobs. If it is open on the career page today, it is in your results; if the
company closed it, it is gone. You pay **$0.99 per 1,000 jobs** (less on Apify's paid plans), and on scheduled runs with **Only new jobs** you
pay only for jobs that are new since the last run.

## Supported job boards

The Career Site Jobs Scraper reads five applicant tracking systems. Mix them freely in one run.

| Platform | Enter | Salary ranges | Company name |
|---|---|---|---|
| Greenhouse | `airbnb` or a `boards.greenhouse.io` / `job-boards.greenhouse.io` URL | Where published | Yes |
| Lever | `lever:zoox` or a `jobs.lever.co` URL (`lever-eu:` for EU boards) | Where published | No (use `board_token`) |
| Ashby | `ashby:ramp` or a `jobs.ashbyhq.com` URL | Where shown on the posting | No (use `board_token`) |
| Workable | `workable:blueground` or an `apply.workable.com/<account>` URL | Not in the public feed | Yes |
| Personio | `personio:tado` or a `<company>.jobs.personio.com` / `.de` URL | Where published | Yes |

### Greenhouse jobs scraper

Enter a Greenhouse board token such as `airbnb` or `stripe`, or paste any `boards.greenhouse.io` or
`job-boards.greenhouse.io` link. You get every open job with its departments, offices, full description and, where
the company publishes pay transparency ranges, the salary range.

### Lever jobs scraper

Enter `lever:<company>` (for example `lever:zoox`) or paste a `jobs.lever.co` link; EU-hosted boards work with
`lever-eu:<company>`. Lever jobs come with employment type, workplace type and, where published, the salary range.

### Ashby jobs scraper

Enter `ashby:<company>` (for example `ashby:ramp` or `ashby:notion`) or paste a `jobs.ashbyhq.com` link. Ashby is
popular with fast-growing tech companies, and many of them show a salary range on every posting.

### Workable jobs scraper

Enter `workable:<account>` (for example `workable:blueground`) or paste an `apply.workable.com` link. Workable jobs
come with the company name, location, department and full description.

### Personio jobs scraper

Enter `personio:<company>` (for example `personio:tado`) or paste a `jobs.personio.com` or `jobs.personio.de` link.
Personio is widely used by European small and mid-sized companies, and its feed includes salary ranges where
published.

## What data do you get?

One result per open job. Every job has the same fields, whichever job board it comes from; a field a platform does
not publish is `null`.

| Field | Description |
|---|---|
| `platform` | `greenhouse`, `lever`, `ashby`, `workable` or `personio` |
| `board_token` | The board the job came from, for example `airbnb` or `zoox` |
| `company` | Company name, from Greenhouse, Workable and Personio (Lever's and Ashby's feeds do not publish it; use `board_token`) |
| `job_id` | The platform's job ID: a number on Greenhouse and Personio, an ID string elsewhere (stable across runs) |
| `internal_job_id` | Greenhouse internal job ID, shared by posts of the same job |
| `requisition_id` | The company's own requisition ID, when it sets one (Greenhouse, Workable) |
| `title` | Job title |
| `location` | Location text of the posting, for example `Tokyo, Japan` or `Remote - US` |
| `department` | First department or team of the job |
| `departments` | All departments (Greenhouse), the department and team (Lever, Ashby), or the department |
| `office` | First office of the job |
| `offices` | All offices or locations of the job |
| `absolute_url` | Link to the job posting where candidates apply |
| `language` | Language code of the posting, for example `en` (Greenhouse) |
| `updated_at` | When the posting was last updated (Greenhouse, ISO 8601 with time zone) |
| `first_published` | When the posting was first published (ISO 8601; a date only on Workable) |
| `content` | Full job description as HTML |
| `content_text` | Full job description as plain text, one paragraph or bullet per line |
| `employment_type` | For example `Full-time`, `Part-time` or `Intern` |
| `workplace_type` | `onsite`, `hybrid` or `remote` (Lever, Ashby; `remote` on Workable) |
| `salary_min`, `salary_max` | Salary range, when the company publishes one (all platforms but Workable) |
| `salary_currency` | For example `USD` |
| `salary_interval` | `per-year-salary`, `per-month-salary`, `per-hour-wage` and so on, or `null` when the board does not say |
| `fetched_at` | When the Actor read the job (UTC) |

With **Include full job descriptions** off, `content` and `content_text` are empty (and, on Greenhouse, the
departments and offices too). The Actor does not return the companies' custom application questions or custom
metadata fields. When a Greenhouse job lists one pay range per country, the salary fields hold the first one. E-mail addresses and phone numbers that appear in a description are replaced with `[removed]`.

## Get a daily feed of new jobs

Turn on **Only new jobs** and [schedule the Actor](https://docs.apify.com/platform/schedules), for example every
morning. The first run returns every open job. After that, each run returns only jobs that were not there before, and
you pay only for those: a day with no new jobs charges no results. The Actor remembers what it returned in your own
Apify account. Runs with the same boards and keywords share that memory, or give them a **Monitor name** to keep one
memory while you add or remove boards. A run that stops early (at **Maximum results** or your spending limit) keeps the
jobs it did not reach for the next run.

## How much does it cost to scrape Greenhouse, Lever, Ashby, Workable and Personio jobs?

You pay per result: $0.99 per 1,000 jobs, plus a small fee per run that Apify sets. On Apify's paid plans it is
cheaper: $0.89 (Bronze), $0.79 (Silver) or $0.69 (Gold) per 1,000. A run of 1,000 jobs costs about $0.99, whichever
platform they come from. Set a maximum cost per run and the Actor stops when it is reached. Use
**Maximum results** and the keyword filters to pay only for the jobs you need; jobs removed by a filter are not charged.

## How to use it

1. Click **Try for free**.
2. Enter one or more job boards: a board name such as `airbnb`, `lever:zoox`, `ashby:ramp`, `workable:blueground` or
   `personio:tado`, or a job board URL from the company's careers page.
3. Click **Start** and download the results when the run finishes.

## Input

- **Job boards** (`boardTokens`, required): the companies to read, on Greenhouse, Lever, Ashby, Workable or Personio.
- **Include full job descriptions** (`includeContent`, default `true`): descriptions, plus departments and offices
  on Greenhouse.
- **Title keywords** (`titleKeywords`): keep jobs whose title contains any of these words.
- **Location keywords** (`locationKeywords`): keep jobs whose location or office contains any of these words.
- **Only new jobs** (`onlyNew`, default `false`): return only jobs earlier runs with the same search did not return.
- **Monitor name** (`monitorName`): optional name that keeps one memory of returned jobs across input changes.
- **Maximum results** (`maxResults`, default 1,000): stop after this many jobs.
- **Maximum requests per second** (`maxRequestsPerSecond`, default and maximum 1): polite rate limit.

```json
{
    "boardTokens": ["airbnb", "https://job-boards.greenhouse.io/stripe", "lever:zoox", "https://jobs.lever.co/palantir", "ashby:ramp",
                    "workable:blueground", "personio:tado"],
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
companies on all five platforms that feeds new `job_id`s into a job board, a CRM, a salary benchmark or a hiring-signals
dashboard.

For AI agents there is a dedicated server: the [Job Search MCP Server](https://apify.com/guayox/ats-jobs-mcp-server) gives Claude, Cursor and other
MCP clients two tools, one that finds which job board a company uses and one that searches its open jobs.

## Related Actors

- [Job Search MCP Server](https://apify.com/guayox/ats-jobs-mcp-server): the same five job boards as tools for AI agents, including CV matching. Ask "is Notion hiring
  designers?" and the agent finds the board and the jobs, with salary ranges.

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
- **Ashby:** the [Public Job Posting API](https://developers.ashbyhq.com/docs/public-job-posting-api)
  (`api.ashbyhq.com`), which returns the jobs a company has published on its public Ashby job board and needs no key.
  Its documentation does not address third-party use either way. Its API answers `/robots.txt` with "401", which
  the robots.txt standard (RFC 9309) treats as "no robots.txt". The Actor returns a salary only when the company
  shows pay on its job posting, and leaves out jobs the company keeps off its board list.
- **Workable:** the public jobs endpoint described in Workable's help centre
  ([Using the Workable API to create a careers page](https://help.workable.com/hc/en-us/articles/115012771647)),
  which lists a company's published jobs without a key. Its robots.txt allows crawling.
- **Personio:** the XML job feed described in Personio's
  [developer documentation](https://developer.personio.de/docs/retrieving-open-job-positions)
  (`<company>.jobs.personio.com/xml`). Its robots.txt allows crawling.

Ashby's, Workable's and Personio's documentation does not address third-party use either way.

The Actor only reads open job postings, needs no login, checks each API's robots.txt before each request, keeps to a
polite request rate, and stores no personal data. Check that your own use of the job postings suits your purpose and
jurisdiction.

**Where do I find a company's board?** Open the company's careers page and click a job.

- If the link goes to `boards.greenhouse.io/<token>/...` or `job-boards.greenhouse.io/<token>/...`, paste the URL or
  the `<token>`. Some companies show Greenhouse jobs on their own site with a `gh_jid=` link; their token is usually
  the company name.
- If it goes to `jobs.lever.co/<company>/...`, paste the URL or enter `lever:<company>`.
- If it goes to `jobs.ashbyhq.com/<company>/...`, paste the URL or enter `ashby:<company>`.
- If it goes to `apply.workable.com/<account>/...`, paste the URL or enter `workable:<account>`.
- If it goes to `<company>.jobs.personio.com/...` or `.de`, paste the URL or enter `personio:<company>`.

**A board returned no jobs.** Either the company has no open jobs or the token is wrong; the run log says
"No Greenhouse board called ..." (or Lever, Ashby, Workable) for an unknown board. For an unknown Personio company
it says that robots.txt does not allow the feed, because Personio blocks crawling on company names it does not host.
Only companies that use one of the five platforms are covered.

**Why is `company` empty for Lever and Ashby jobs?** Their public APIs do not include the company's display name.
Every job carries its `board_token` (for example `zoox` or `ramp`), which identifies the company.

**How fresh is the data?** Every run fetches it live from the source.

**Something is not working.** Open an issue on the Actor's **Issues** tab; it is monitored daily.
