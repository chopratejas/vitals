# Trend Tracking

Trend tracking is what turns Vitals from a one-shot tool into something you run every week.

## How It Works

Every time you run `/vitals:scan`, Vitals saves a health snapshot to `.vitals/store.db` (once per calendar day). The next time you scan, it compares the current state to the previous snapshot and shows what changed.

```
TRENDS — since 1 week ago

  Overall: 6.8 ↓ 5.4  (-1.4)

  DEGRADING
    src/transforms/router.py     4.5 → 2.8  (-1.7)
    src/auth/session.py          7.1 → 5.2  (-1.9)

  IMPROVING
    src/utils/validators.py      3.1 → 5.8  (+2.7)
```

## What Gets Tracked

Each snapshot stores:

- **Overall codebase health** (single number, 1-10)
- **Per-file health scores** for every file with structural complexity
- **Complexity scores** and **file roles** (core/test)
- **Timestamp** for time-series comparison

## Snapshot Rules

- **One snapshot per day**: Multiple scans on the same day don't create duplicates
- **Scoped snapshots**: Scoping to a directory (e.g., `/vitals:scan src/auth`) saves a separate snapshot for that scope
- **Only when plugin is installed**: Snapshots are only saved if `.vitals/` exists (created by the provenance capture hook on first AI edit). Running the standalone CLI on a fresh repo doesn't create any files

## Change Thresholds

A file appears in the DEGRADING or IMPROVING list when its health score changes by more than **0.5 points**. Smaller fluctuations are noise and are ignored.

## Use Cases

### Weekly Health Check

Run `/vitals:scan` every Monday. Over time, you'll see:

- Whether your refactoring efforts are paying off
- Which files are silently degrading while attention is elsewhere
- Whether new features are introducing debt faster than you're paying it off

### Sprint Retrospectives

Compare health before and after a sprint to measure the impact of technical debt work.

### New Team Member Onboarding

Show a new developer the trend history so they understand which areas of the codebase are improving and which need attention.
