# Vitals

**Your codebase has a health score. You just can't see it yet.**

Vitals is a Claude Code plugin that finds the files most likely to cause your next outage, reads them, diagnoses root causes, and tells you exactly what to fix first.

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

TRENDS — since 1 week ago
  Overall: 6.8 ↓ 5.4  (-1.4)
  DEGRADING
    src/transforms/router.py     4.5 → 2.8  (-1.7)
  IMPROVING
    src/utils/validators.py      3.1 → 5.8  (+2.7)

TOP RECOMMENDATION
  src/proxy/server.py is your #1 priority: 7,137 lines, health 2.3,
  49 changes in 90 days, co-changes with 63 other files.
```

## Why Vitals?

41% of all code is now AI-generated. Refactoring has collapsed from 25% to under 10%. Code churn is at historic highs. Yet no tool answers:

> *"At the current trajectory, when does this module become a liability? And what's the most impactful thing to fix right now?"*

Vitals answers that question.

## Quick Start

```
/plugin marketplace add chopratejas/vitals
/plugin install vitals@vitals
/vitals:scan
```

No API keys. No configuration. No external dependencies.

[Get Started](getting-started.md){ .md-button .md-button--primary }
[How It Works](how-it-works.md){ .md-button }
