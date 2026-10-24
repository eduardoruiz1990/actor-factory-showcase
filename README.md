# Actor Factory

Agents that find, build, publish and maintain paid Actors on the [Apify Store](https://apify.com/store), with a human approving the key steps. The specification is in [docs/SPEC.md](docs/SPEC.md).

| Agent | When | Status |
|---|---|---|
| Scout | Weekly: reads the Apify Store and Ideas page, opens an issue with 20 candidate niches | Phase 1 ✅ |
| Validator | After each Scout run: scores every candidate on five checks with `claude-sonnet-5-5` and posts a brief | Phase 1 ✅ |
| Builder | `go` label: the Claude Code GitHub Action opens a pull request with a new Actor | Phase 2 |
| Publisher | Merge to `main`: `apify push` and Store listing text | Phase 2 |
| Watcher | Daily: runs, failures, reviews and revenue; opens `broken` issues | Phase 3 |
| Fixer | `broken` label: a fix pull request with a test that reproduces the failure | Phase 3 |
| Digest | Mondays: a one-page email | Phase 4 |

## Quick start

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/python -m factory.dry_run      # writes out/dry-run/issue_preview.md from sample data
```

Thresholds are in [config.yaml](config.yaml). Open questions are in [docs/QUESTIONS.md](docs/QUESTIONS.md). Conventions for Claude Code are in [CLAUDE.md](CLAUDE.md).

## Secrets

Set these in GitHub Actions secrets only: `APIFY_TOKEN`, `ANTHROPIC_API_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `DIGEST_TO`. See [.env.example](.env.example).
