# Architecture

Vitals is 13 files with zero external dependencies.

## Project Structure

```
vitals/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest
│   └── marketplace.json         # Marketplace catalog
├── skills/
│   └── scan/
│       └── SKILL.md             # /vitals:scan — Claude's analysis instructions
├── hooks/
│   └── hooks.json               # PostToolUse (provenance) + Stop (session health)
├── scripts/
│   ├── vitals_cli.py            # CLI entry point and orchestrator
│   ├── git_analysis.py          # Churn, coupling, knowledge from git
│   ├── complexity.py            # AST (Python) + indentation (all languages)
│   ├── health_score.py          # Composite 1-10 scoring
│   ├── provenance.py            # Silent AI edit tracking (hook handler)
│   ├── db.py                    # SQLite operations (provenance + snapshots)
│   └── report.py                # Terminal report formatting
├── LICENSE
└── README.md
```

## Data Flow

```
/vitals:scan
     │
     ▼
┌─────────────────────────────────┐
│  SKILL.md instructs Claude to:  │
│  1. Run vitals_cli.py --json    │
│  2. Read top hotspot files      │
│  3. Diagnose root causes        │
│  4. Present ROI-ranked report   │
└───────┬─────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│  vitals_cli.py orchestrates:    │
│  ├─ git_analysis.py (churn,     │
│  │   coupling, knowledge)       │
│  ├─ complexity.py (nesting,     │
│  │   structure)                 │
│  ├─ health_score.py (composite  │
│  │   1-10 scoring)              │
│  ├─ db.py (read provenance,     │
│  │   save snapshot)             │
│  └─ report.py (format output)  │
└───────┬─────────────────────────┘
        │
        ▼
  Structured JSON → Claude reads
  hotspot files → Diagnosis
```

## Design Principles

### Zero Dependencies

The entire plugin is Python stdlib + git. No pip install, no npm, no API keys. If you have Python 3 and a terminal, it works. This is a deliberate constraint — every dependency is a friction point that reduces adoption.

### Zero Regex

Complexity is measured by indentation depth, not language-specific keyword patterns. File filtering uses structural signals (has extension? hidden directory? lock file?) and git-native detection (linguist-generated). No brittle pattern matching.

### Read-Only by Default

The `report` command never creates directories or modifies files. The `.vitals/` directory is only created by the provenance capture hook on the first AI edit. Health snapshots are only saved if `.vitals/` already exists.

### Git Optional

With git: full analysis (churn, coupling, knowledge, complexity, trends). Without git: complexity-only scan. The tool never crashes — it degrades gracefully.

### Monorepo-Safe

Churn data is computed first, then complexity is computed only for churning files, and non-code is filtered before ranking. Lock files and generated code never drown out real hotspots, even in repos with 200+ dependency manifests.

### Claude is the Brain

The Python scripts do triage — they identify WHERE to look. Claude does diagnosis — it reads the actual code and tells you WHAT's wrong and HOW to fix it. This is fundamentally different from tools that compute metrics and dump a report.

## Storage

All data lives in `.vitals/store.db` (SQLite with WAL mode):

| Table | Purpose | Growth |
|-------|---------|--------|
| `provenance_events` | AI edit tracking | ~1-5 KB per edit |
| `session_summary` | Session aggregates | ~200 bytes per session |
| `health_snapshots` | Trend tracking (overall) | ~100 bytes per scan |
| `file_snapshots` | Trend tracking (per-file) | ~50 bytes per file per scan |

Typical annual storage: **1-3 MB** per active project.
