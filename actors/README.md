# Actors

One folder per Actor: `actors/<name>/`. The Builder creates each one from the official Apify Python template, with code, tests, an input schema, a Store README and pay-per-event pricing per result (Phase 2).

Every Actor must use polite rate limits, retry with back-off, respect robots.txt and output no personal data. See [CLAUDE.md](../CLAUDE.md).
