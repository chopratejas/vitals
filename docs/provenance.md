# AI Provenance

From the moment Vitals is installed, it silently tracks every AI-generated code edit. This is the data moat that enables future features like drift detection and decay prediction.

## What Gets Captured

Every time Claude Code edits or writes a file, the PostToolUse hook logs:

| Field | Description |
|-------|-------------|
| `file_path` | Which file was modified (repo-relative) |
| `tool_name` | `Edit` or `Write` |
| `lines_changed` | Estimated lines affected |
| `session_id` | Which Claude Code session made the change |
| `timestamp` | When the change happened |

## What Does NOT Get Captured

| Data | Stored? | Why |
|------|---------|-----|
| Raw prompts | **No** | Privacy — prompts may contain sensitive info |
| Full file contents | **No** | Redundant — git is the source of truth |
| Code diffs | **No** | Same as git |
| API keys or secrets | **No** | Never touches environment variables |

## How It Works

```
Claude Code Edit/Write
        │
        ▼
PostToolUse hook (async, <100ms)
        │
        ▼
provenance.py capture
        │
        ▼
.vitals/store.db (SQLite, WAL mode)
```

The hook is **async** — it runs in the background and never blocks Claude Code. The developer never notices it.

## What Shows Up in Reports

After provenance data accumulates, `/vitals:scan` shows an AI section:

```
AI PROVENANCE — Code Generation Tracking

  Tracking for 14 days: 47 AI edits across 12 files in 8 sessions

  Most AI-modified files:
    src/api/handlers.py               12 AI changes (8 edits, 4 writes)
    src/auth/oauth.py                  7 AI changes (5 edits, 2 writes)
    src/models/user.py                 5 AI changes (4 edits, 1 write)
```

## Privacy Architecture

- **Local-first**: All data stays in `.vitals/store.db` on your machine
- **No network calls**: Zero data leaves your system
- **Gitignored**: `.vitals/` is added to `.gitignore` automatically
- **No raw prompts**: Only metadata about edits, never the conversation content

## Storage

The SQLite database uses WAL mode for concurrent access and typically grows to 1-3 MB per year of active use. The data is compact:

- ~1-5 KB per provenance event
- ~200 bytes per health snapshot
- Total: negligible disk usage

## Future: What Provenance Enables

The provenance data being collected now will power future Vitals features:

- **Drift detection** (v0.3) — compare original intent vs. current state
- **Decay prediction** (v0.4) — predict when a module becomes unmaintainable
- **AI code ratio** — track what percentage of your codebase is AI-generated
- **Churn correlation** — identify which AI-generated code gets revised most
