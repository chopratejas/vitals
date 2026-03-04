# Vitals

**Your codebase has a health score. You just can't see it yet.**

Vitals is a Claude Code plugin that finds the files most likely to cause your next outage, explains *why* they're dangerous, and tells you exactly what to fix first.

It's not a linter. It's not a static analysis tool. It reads your code, thinks about it, and gives you a diagnosis — like a doctor, not a thermometer.

```
/vitals:scan

Overall Health: 5.4 / 10.0  ██████████░░░░░░░░░░

HOTSPOTS — Ranked by ROI (core > test, central > leaf)

File                                   Health  Role  Complexity  Churn  Links
───────────────────────────────────────────────────────────────────────────
src/proxy/server.py                      2.3  core   100        49/90d    63
src/transforms/content_router.py         2.8  core    98        17/90d    35
src/transforms/smart_crusher.py          2.8  core   100        16/90d    12

TOP RECOMMENDATION
  src/proxy/server.py is your #1 priority: 7,137 lines, health 2.3 (alert zone),
  49 changes in 90 days, co-changes with 63 other files.
  This file handles routing, caching, rate limiting, cost tracking, AND metrics
  in a single class. Extract each concern into its own module.
```

## Install

In Claude Code, run:

```
/plugin marketplace add chopratejas/vitals
/plugin install vitals@vitals
```

Then:

```
/vitals:scan
/vitals:scan src/auth          # scope to a directory
/vitals:scan --top 20          # show more hotspots
```

No API keys. No configuration. No external dependencies. Just Python 3 and a codebase.

## What It Does

### Phase 1: Quantitative Triage (Python)

A fast metrics scan identifies WHERE to look:

- **Hotspot Detection** — Files ranked by `churn x complexity x centrality`. Not just "what's complex" but "what's complex AND changing frequently AND connected to everything else."
- **Co-Change Coupling** — Files that always change together, revealing hidden architectural dependencies.
- **Knowledge Risk** — Bus factor analysis. Which files have only one contributor? What happens when they leave?
- **ROI Ranking** — Core production code with high centrality ranks above tests and leaf utilities. Because fixing a central engine has 10x the impact of fixing an isolated helper.

### Phase 2: Deep Analysis (Claude)

Claude reads the top hotspot files and **diagnoses root causes**:

- Not "high complexity" but *"this function handles validation, transformation, AND persistence in one 200-line loop"*
- Not "strong coupling" but *"these files share a global config dict — introduce dependency injection"*
- Not "low health score" but *"only one person contributes because the code is so tangled others avoid it"*

The metrics tell Claude where to look. Claude tells you what's actually wrong.

### Phase 3: Silent Provenance Capture (Background)

From the moment you install, Vitals silently tracks every AI-generated edit:

- Which files are being modified by AI
- How frequently each file is touched
- The ratio of AI-generated to human-authored changes

This data accumulates over time. After a week of use, `/vitals:scan` shows AI-specific insights — which files are churning under AI edits, which modules are being regenerated instead of maintained.

## How It Works

```
Developer runs /vitals:scan
         │
         ▼
    ┌─────────────────────────────────────┐
    │  Phase 1: Python metrics script     │
    │  ├─ git log → churn analysis        │
    │  ├─ indentation → complexity gate   │
    │  ├─ co-change → coupling detection  │
    │  ├─ shortlog → knowledge risk       │
    │  └─ Output: structured JSON         │
    └──────────────┬──────────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────────┐
    │  Phase 2: Claude reads hotspots     │
    │  ├─ Reads top 3 core files          │
    │  ├─ Diagnoses root causes           │
    │  ├─ Assesses blast radius           │
    │  └─ Prescribes specific fixes       │
    └──────────────┬──────────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────────┐
    │  Report: ROI-ranked action plan     │
    │  ├─ Core hotspots with diagnosis    │
    │  ├─ Coupling issues explained       │
    │  ├─ Knowledge risk assessment       │
    │  └─ "Fix this first" ranked list    │
    └─────────────────────────────────────┘

Meanwhile, in the background:
    PostToolUse hook → captures every AI edit → .vitals/store.db
```

## Design Principles

**Zero dependencies.** No pip install. No npm. No API keys. The entire plugin is Python stdlib + git. If you have Python 3 and a terminal, it works.

**Zero regex.** Complexity is measured by indentation depth, not language-specific keyword patterns. This works for Python, Java, Scala, Go, TypeScript, Rust — any language with indentation. The nesting gate (`depth <= 2 = not code`) filters lock files, configs, and data files without maintaining a brittle extension list.

**Zero hardcoded lists.** No list of "source file extensions." No list of "ignored directories." File filtering uses structural signals (has an extension? in a hidden directory? is a `.lock` file?) and git-native detection (`linguist-generated` from `.gitattributes`).

**Git optional.** With git: full analysis (churn, coupling, knowledge risk, complexity). Without git: complexity-only scan. The tool never crashes — it degrades gracefully.

**Monorepo-safe.** Tested on repos with 34,000+ commits and 268 contributors. The analysis flow computes churn first, filters to source files, then computes complexity — so lock files and generated code never drown out real hotspots.

**Claude is the brain, not a presenter.** The Python script does triage. Claude does diagnosis. Other tools compute metrics and dump a report. Vitals hands Claude the exact files to read, and Claude tells you what's actually wrong and how to fix it.

## What Makes a Hotspot

A hotspot is a file where **churn AND complexity AND centrality** intersect:

| Signal | What It Measures | Source |
|--------|-----------------|--------|
| **Churn** | How often the file changes (last 90 days) | `git log --numstat` |
| **Complexity** | Nesting depth and structural density | Indentation analysis (Python AST for `.py`) |
| **Centrality** | How many other files co-change with it | Co-change coupling pairs |
| **Role** | Core production code vs. test vs. config | Path conventions (`/test/`, `_test.py`, `Test.java`) |

The risk score formula:

```
risk = (10 - health) × churn × role_weight × (1 + centrality × 0.2)
```

Core files with high centrality dominate the list. Tests are weighted 0.3x. A moderately unhealthy core engine that 40 files depend on ranks far above a critically unhealthy test that nothing imports.

## Health Score

Each file gets a health score from 1.0 to 10.0:

| Score | Category | Meaning |
|-------|----------|---------|
| 9-10 | Healthy | Well-structured, low risk |
| 7-9 | Good | Minor issues, monitor |
| 4-7 | Warning | Accumulating debt, plan refactoring |
| 1-4 | Alert | High defect risk (research shows 15x more bugs) |

The score combines:
- **Complexity** (30%) — nesting depth, deep-nesting density
- **Churn** (30%) — change frequency in last 90 days
- **Coupling** (20%) — strength of co-change relationships
- **Knowledge** (20%) — truck factor (how many people must leave before knowledge is lost)

## Provenance Capture

Every AI-generated edit is silently logged:

```
PostToolUse(Edit|Write) → .vitals/store.db
```

What's captured:
- File path, tool name (Edit/Write), timestamp, session ID, lines changed

What's NOT captured:
- Raw prompts (never stored — only a one-way hash for correlation)
- Full file contents (only diffs, same as git)
- No network calls (all data stays local)

The database lives at `.vitals/store.db` in your project root, gitignored by default.

After provenance data accumulates, `/vitals:scan` shows:
- Which files are heavily AI-modified
- AI edit frequency per file
- Ratio of AI-generated to human-authored changes

## Standalone CLI

Vitals also works as a standalone CLI tool, outside of Claude Code:

```bash
# In any git repo:
python3 /path/to/vitals/scripts/vitals_cli.py report

# Scope to a directory:
python3 /path/to/vitals/scripts/vitals_cli.py report src/auth

# JSON output (for piping to other tools):
python3 /path/to/vitals/scripts/vitals_cli.py report --json

# Show more hotspots:
python3 /path/to/vitals/scripts/vitals_cli.py report --top 20

# Works without git too (complexity-only scan):
python3 /path/to/vitals/scripts/vitals_cli.py report /path/to/any/directory
```

## Project Structure

```
vitals/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── skills/
│   └── scan/
│       └── SKILL.md             # /vitals:scan — Claude's analysis instructions
├── hooks/
│   └── hooks.json               # PostToolUse (provenance) + Stop (session assessment)
├── scripts/
│   ├── vitals_cli.py          # CLI entry point and orchestrator
│   ├── git_analysis.py           # Churn, coupling, knowledge from git
│   ├── complexity.py             # AST (Python) + indentation (all languages)
│   ├── health_score.py           # Composite 1-10 scoring
│   ├── provenance.py             # Silent AI edit tracking
│   ├── db.py                     # SQLite provenance storage
│   └── report.py                 # Terminal report formatting
```

10 files. Zero external dependencies. That's the entire tool.

## Why This Exists

41% of all code is now AI-generated. Refactoring has collapsed from 25% to under 10% of code changes. Code churn is at historic highs. Maintenance costs for unmanaged AI code reach 4x traditional levels by year two.

Every existing tool is either reactive (finds problems after they exist), snapshot-based (measures code health at one point in time), or PR-scoped (reviews individual changes without codebase context).

No tool answers: *"At the current trajectory, when does this module become a liability? And what's the most impactful thing to fix right now?"*

Vitals is building toward that answer. The metrics are the foundation. The provenance data is the moat. Claude's reasoning is the differentiator.

## Roadmap

- [x] **v0.1** — Health scoring, hotspot detection, coupling, knowledge risk, provenance capture
- [ ] **v0.2** — Trend tracking (health snapshots over time: "your codebase went from 7.2 → 4.8 this month")
- [ ] **v0.3** — Drift detection (compare original intent vs. current state using provenance data)
- [ ] **v0.4** — Decay prediction (per-module liability dates: "this file becomes unmaintainable in ~47 days")
- [ ] **v1.0** — SaaS dashboard with team-level insights and cross-repo trends

## Contributing

Vitals is MIT licensed. Contributions welcome.

Before contributing:
- Keep the zero-dependency constraint. If it's not in Python's stdlib, it doesn't go in.
- No regex for file classification. Structural signals only.
- Test against a real repo with 100+ files before submitting.

```bash
# Run against any git repo to test:
cd /path/to/your/repo
python3 /path/to/vitals/scripts/vitals_cli.py report
```

## License

MIT
