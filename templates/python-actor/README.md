<!--
Store README skeleton (Actor Factory). This file is the Actor's page on Apify Store
and the text Google and AI agents read, so write it for a buyer, not a developer.
Replace every TODO, keep the section order, delete these comments.
The structure follows Apify's README guide:
https://docs.apify.com/academy/actor-marketing-playbook/actor-basics/how-to-create-an-actor-readme
-->

# TODO Actor title: what it extracts, from where

TODO One paragraph: what data the Actor returns, from which public source, and who uses it. Put the main
keywords a buyer would search for in the first two sentences.

## What can this Actor do?

- TODO The main capability (for example "Get every open job from any company's Greenhouse board")
- TODO Filters or options a buyer cares about
- **Only new results:** schedule it with **Only new results** on, and each run returns and charges only what is new since the last run
- Polite by design: it respects robots.txt and rate limits, and retries with back-off
- No personal data: names, e-mail addresses and phone numbers are never stored
- Export to JSON, CSV, Excel or HTML, or connect through the Apify API, integrations and MCP

## What data do you get?

| Field | Description |
|---|---|
| `url` | TODO |
| `title` | TODO |

## Get a feed of new results

Turn on **Only new results** and [schedule the Actor](https://docs.apify.com/platform/schedules). The first run
returns everything; after that, each run returns and charges only results earlier runs did not return. A run with
nothing new charges no results. TODO Say what "new" means for this source (for example "newly posted jobs").

## How much does it cost to TODO scrape <source>?

You pay per result: TODO $X.XX per 1,000 results, plus a small fee per run that Apify sets. A run of 1,000
results costs about TODO $X. Set a maximum cost per run and the Actor stops when it is reached.

## How to use it

1. Click **Try for free**.
2. TODO Enter the input (for example a list of company board tokens).
3. Click **Start** and download the results when the run finishes.

## Input

TODO A short description of each input field. Example:

```json
{
    "startUrls": [{ "url": "https://example.com/" }],
    "maxResults": 100
}
```

## Output example

```json
{
    "url": "https://example.com/",
    "title": "TODO",
    "fetchedAt": "2026-01-01T00:00:00+00:00"
}
```

## Use it through the API or AI agents

Call the Actor from your code with the [Apify API](https://docs.apify.com/api/v2), or from an AI agent through
[Apify's MCP server](https://mcp.apify.com). TODO one sentence on a typical automated use.

## Related Actors

- TODO Link the factory's other Actors in the same category or for the same users, one line each on when to use it.

## FAQ

**Is it legal to use this data?** TODO Name the source and the terms that allow automated access and reuse,
with a link. The Actor reads only public pages or official APIs, needs no login, and stores no personal data.

**How fresh is the data?** Every run fetches it live from the source.

**Something is not working.** Open an issue on the Actor's **Issues** tab; it is monitored daily.
