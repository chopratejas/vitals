# How It Works

Vitals runs in two phases: **metrics triage** (Python, fast) and **deep analysis** (Claude, intelligent).

## Phase 1: Quantitative Triage

A Python script analyzes your git history and code structure:

```
Developer runs /vitals:scan
         │
         ▼
    ┌─────────────────────────────────────┐
    │  Python metrics script              │
    │  ├─ git log → churn analysis        │
    │  ├─ indentation → complexity gate   │
    │  ├─ co-change → coupling detection  │
    │  ├─ shortlog → knowledge risk       │
    │  └─ Output: structured JSON         │
    └──────────────┬──────────────────────┘
                   ▼
         Only real code survives.
         Lock files, configs, data = filtered out.
```

### What Gets Filtered

The metrics script uses a three-layer filter to ensure only real source code reaches the hotspot list:

1. **Structural filter** — removes lock files (`.lock`, `.lockfile`), hidden directories, files without extensions
2. **Git-native filter** — respects `.gitattributes` `linguist-generated` markers
3. **Complexity gate** — files with nesting depth <= 2 score zero (eliminates configs, prose, flat data)

This means `uv.lock`, `package-lock.json`, `pyproject.toml`, `README.md`, and generated code never appear in your hotspot list — even in monorepos with hundreds of lock files.

### ROI-Aware Ranking

Hotspots aren't just ranked by health score. The risk formula:

```
risk = (10 - health) × churn × role_weight × centrality_boost
```

| Factor | What it captures |
|--------|-----------------|
| `10 - health` | How unhealthy the file is |
| `churn` | How frequently it changes (last 90 days) |
| `role_weight` | Core code = 1.0, test files = 0.3 |
| `centrality_boost` | 1 + (coupling_partners × 0.2) |

A moderately unhealthy core engine that 40 files depend on ranks far above a critically unhealthy test that nothing imports.

## Phase 2: Deep Analysis

Claude reads the top hotspot files and diagnoses root causes:

```
    ┌─────────────────────────────────────┐
    │  Claude reads hotspots              │
    │  ├─ Reads top 3 core files          │
    │  ├─ Diagnoses root causes           │
    │  ├─ Assesses blast radius           │
    │  └─ Prescribes specific fixes       │
    └──────────────┬──────────────────────┘
                   ▼
         Actionable, ROI-ranked report.
```

This is what makes Vitals different from every other code quality tool:

- **Not** "high complexity" → "This function handles validation, transformation, AND persistence in one 200-line loop"
- **Not** "strong coupling" → "These files share a global config dict — introduce dependency injection"
- **Not** "low health score" → "Only one person contributes because the code is so tangled others avoid it"

The metrics tell Claude **where** to look. Claude tells you **what's actually wrong**.

## Background: Provenance Capture

From the moment Vitals is installed, a PostToolUse hook silently captures every AI-generated edit:

```
Claude Code edit → PostToolUse hook (async) → .vitals/store.db
```

This runs in the background with zero impact on developer experience. The data accumulates over time, enabling AI-specific insights in future scans.

## No LLMs Required

Vitals uses **zero external API calls**. The Phase 1 metrics script is pure Python stdlib + git. Phase 2 uses Claude Code's built-in Claude access via the skill system — no API key, no cost, no configuration.
