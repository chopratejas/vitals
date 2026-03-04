# Privacy Policy

**Last updated:** March 4, 2026

## Summary

Vitals collects zero data from your machine. Everything stays local.

## What Vitals Stores

Vitals stores provenance metadata in `.vitals/store.db` inside your project directory:

- File paths that were edited by AI (repo-relative, e.g., `src/auth/handler.py`)
- Tool name (`Edit` or `Write`)
- Timestamps and session IDs
- Line change estimates
- Health score snapshots for trend tracking

## What Vitals Does NOT Store

- **Prompts or conversations** — never captured
- **File contents or diffs** — never duplicated (git is the source of truth)
- **API keys, secrets, or credentials** — never accessed
- **Personal information** — no names, emails, or identifiers beyond git author names already in your repo's public history

## No Network Activity

Vitals makes **zero network calls**. No telemetry, no analytics, no phone-home, no API calls. All processing happens locally using Python's standard library and git commands.

## No External LLMs

Vitals does not call OpenAI, Anthropic, or any other external API. The deep analysis phase uses Claude Code's built-in Claude access via the skill system — the same Claude instance you're already running. No additional API keys or costs.

## Data Location

All data lives in `.vitals/store.db` (SQLite) inside your project root. This directory is automatically added to `.gitignore` so it is never committed or shared.

You can delete all Vitals data at any time:

```bash
rm -rf .vitals/
```

## Open Source

Vitals is fully open source under the MIT license. You can audit every line of code at [github.com/chopratejas/vitals](https://github.com/chopratejas/vitals).

## Contact

For privacy questions: chopratejas@gmail.com
