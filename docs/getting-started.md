# Getting Started

## Install

In Claude Code, run:

```
/plugin marketplace add chopratejas/vitals
/plugin install vitals@vitals
```

That's it. No API keys, no pip install, no configuration.

## Your First Scan

```
/vitals:scan
```

Vitals runs in two phases:

1. **Quantitative triage** — a Python script analyzes your git history and code structure to identify hotspots
2. **Deep analysis** — Claude reads the top hotspot files and diagnoses root causes

The result is an ROI-ranked action plan: what to fix, why, and in what order.

## Scope to a Directory

For monorepos or large codebases, scope the analysis:

```
/vitals:scan src/auth
/vitals:scan services/api
```

## Show More Hotspots

```
/vitals:scan --top 20
```

## Standalone CLI

Vitals also works outside Claude Code as a standalone CLI:

```bash
# In any git repo:
python3 /path/to/vitals/scripts/vitals_cli.py report

# Scoped:
python3 /path/to/vitals/scripts/vitals_cli.py report src/auth

# JSON output (pipe to other tools):
python3 /path/to/vitals/scripts/vitals_cli.py report --json

# Works without git too (complexity-only scan):
python3 /path/to/vitals/scripts/vitals_cli.py report /path/to/any/directory
```

## What You'll See

### First Run

Your first scan shows:

- **Overall health score** (1-10)
- **Hotspots** — files ranked by risk, with role (core/test) and centrality (coupling links)
- **Coupling** — files that always change together
- **Knowledge risk** — files with a bus factor of 1
- **Top recommendation** — the single most impactful thing to fix

### Second Run (and Beyond)

After your first scan, Vitals saves a health snapshot. The next time you run it, you'll see **trends**:

```
TRENDS — since 1 week ago
  Overall: 6.8 ↓ 5.4  (-1.4)

  DEGRADING
    src/transforms/router.py     4.5 → 2.8  (-1.7)
  IMPROVING
    src/utils/validators.py      3.1 → 5.8  (+2.7)
```

This is the "aha moment" — you can see whether your codebase is getting healthier or accumulating debt over time.

## Requirements

- **Python 3.8+** (uses only stdlib — no pip install needed)
- **Git** (for churn, coupling, and knowledge analysis)
- **Claude Code** (for the plugin and deep analysis)

Without git, Vitals falls back to complexity-only mode — still useful for analyzing downloaded codebases or zip files.
