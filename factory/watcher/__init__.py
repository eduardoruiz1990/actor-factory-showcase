"""Watcher (Phase 3, not built yet; mcp_check.py is its one piece so far).

Daily: pull runs, failures, reviews and revenue for the owner's Actors through
the Apify API (APIFY_TOKEN), open an issue labelled "broken" when the 24-hour
failure rate passes watcher.broken_failure_rate_24h_above in config.yaml, and
write a Markdown summary that the next Scout run includes
(python -m factory.scout --watcher-summary <file>).
"""
