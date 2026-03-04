"""
Vitals — SQLite database operations.
Stores AI provenance events and session summaries.
Zero external dependencies (uses Python's built-in sqlite3).
"""

import os
import sqlite3
import time
import uuid
from datetime import datetime

SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS provenance_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    file_path TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    lines_changed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_summary (
    session_id TEXT PRIMARY KEY,
    started_at REAL,
    ended_at REAL,
    files_touched INTEGER DEFAULT 0,
    total_edits INTEGER DEFAULT 0,
    total_writes INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_prov_file ON provenance_events(file_path);
CREATE INDEX IF NOT EXISTS idx_prov_session ON provenance_events(session_id);
CREATE INDEX IF NOT EXISTS idx_prov_timestamp ON provenance_events(timestamp);

CREATE TABLE IF NOT EXISTS health_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    overall_health REAL NOT NULL,
    files_scored INTEGER NOT NULL,
    scope TEXT
);

CREATE TABLE IF NOT EXISTS file_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL REFERENCES health_snapshots(snapshot_id),
    file_path TEXT NOT NULL,
    health_score REAL NOT NULL,
    complexity_score INTEGER DEFAULT 0,
    role TEXT DEFAULT 'core'
);

CREATE INDEX IF NOT EXISTS idx_file_snap_path ON file_snapshots(file_path);
CREATE INDEX IF NOT EXISTS idx_file_snap_sid ON file_snapshots(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_health_snap_ts ON health_snapshots(timestamp);
"""


def get_db_path(repo_path):
    """
    Get the path to the vitals database. Read-only — does NOT create
    directories or modify .gitignore. Use ensure_db_dir() for writes.
    """
    return os.path.join(repo_path, ".vitals", "store.db")


def ensure_db_dir(repo_path):
    """
    Create the .vitals/ directory and add it to .gitignore.
    Only call this when actually writing data (provenance capture),
    never on read-only report commands.
    """
    db_dir = os.path.join(repo_path, ".vitals")
    os.makedirs(db_dir, exist_ok=True)

    gitignore_path = os.path.join(repo_path, ".gitignore")
    _ensure_gitignored(gitignore_path)

    return os.path.join(db_dir, "store.db")


def _ensure_gitignored(gitignore_path):
    """Add .vitals/ to .gitignore if not already present."""
    entry = ".vitals/"
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            lines = f.readlines()
        # Line-based check (not substring match)
        if any(line.strip() == entry or line.strip() == entry.rstrip("/") for line in lines):
            return
        with open(gitignore_path, "a") as f:
            if lines and not lines[-1].endswith("\n"):
                f.write("\n")
            f.write(f"\n# Vitals provenance data\n{entry}\n")
    else:
        with open(gitignore_path, "w") as f:
            f.write(f"# Vitals provenance data\n{entry}\n")


def get_connection(db_path):
    """Get a SQLite connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(db_path, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path):
    """Initialize the database schema. Creates the file if needed."""
    db_dir = os.path.dirname(db_path)
    os.makedirs(db_dir, exist_ok=True)

    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("version", str(SCHEMA_VERSION)),
        )
        conn.commit()
    finally:
        conn.close()


def insert_provenance_event(db_path, event_id, session_id, timestamp,
                            file_path, tool_name, lines_changed=0):
    """Insert a single provenance event."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO provenance_events
               (event_id, session_id, timestamp, file_path, tool_name, lines_changed)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_id, session_id, timestamp, file_path, tool_name, lines_changed),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_session_summary(db_path, session_id, files_touched, total_edits, total_writes):
    """Insert or update a session summary."""
    now = time.time()
    conn = get_connection(db_path)
    try:
        existing = conn.execute(
            "SELECT started_at FROM session_summary WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE session_summary
                   SET ended_at = ?, files_touched = ?, total_edits = ?, total_writes = ?
                   WHERE session_id = ?""",
                (now, files_touched, total_edits, total_writes, session_id),
            )
        else:
            conn.execute(
                """INSERT INTO session_summary
                   (session_id, started_at, ended_at, files_touched, total_edits, total_writes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, now, now, files_touched, total_edits, total_writes),
            )
        conn.commit()
    finally:
        conn.close()


def get_ai_file_stats(db_path, days=30):
    """Get AI-modified file statistics from provenance data."""
    cutoff = time.time() - (days * 86400)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT
                 file_path,
                 SUM(CASE WHEN tool_name = 'Edit' THEN 1 ELSE 0 END) as edit_count,
                 SUM(CASE WHEN tool_name = 'Write' THEN 1 ELSE 0 END) as write_count,
                 MAX(timestamp) as last_modified,
                 COUNT(*) as total_events
               FROM provenance_events
               WHERE timestamp > ?
               GROUP BY file_path
               ORDER BY total_events DESC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_provenance_summary(db_path):
    """Get overall provenance collection summary."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """SELECT
                 COUNT(*) as total_events,
                 COUNT(DISTINCT file_path) as unique_files,
                 COUNT(DISTINCT session_id) as total_sessions,
                 MIN(timestamp) as first_event,
                 MAX(timestamp) as last_event
               FROM provenance_events"""
        ).fetchone()
        if row and row["total_events"] > 0:
            return dict(row)
        return None
    finally:
        conn.close()


def has_provenance_data(db_path):
    """Check if any provenance data exists. Safe against corrupt/missing tables."""
    if not os.path.exists(db_path):
        return False
    try:
        conn = get_connection(db_path)
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM provenance_events").fetchone()
            return row["cnt"] > 0
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return False


# ---------------------------------------------------------------------------
# Health Snapshots (Trend Tracking)
# ---------------------------------------------------------------------------

def save_snapshot(db_path, overall_health, file_health_scores, scope=None,
                  complexity_data=None, role_data=None):
    """
    Save a health snapshot for trend tracking.
    Creates the DB if the .vitals/ directory exists (user opted in via plugin).
    Skips if a snapshot was already saved today (same calendar day).
    """
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        return  # .vitals/ doesn't exist — user hasn't installed the plugin

    # Create/migrate DB as needed
    if not os.path.exists(db_path):
        init_db(db_path)
    else:
        _migrate_if_needed(db_path)

    now = time.time()

    conn = get_connection(db_path)
    try:
        # Dedup: skip if a snapshot exists from today
        today_start = _today_start_timestamp()
        existing = conn.execute(
            """SELECT snapshot_id FROM health_snapshots
               WHERE timestamp >= ? AND (scope IS ? OR scope = ?)
               LIMIT 1""",
            (today_start, scope, scope),
        ).fetchone()
        if existing:
            return  # Already snapshotted today

        snapshot_id = str(uuid.uuid4())

        conn.execute(
            """INSERT INTO health_snapshots
               (snapshot_id, timestamp, overall_health, files_scored, scope)
               VALUES (?, ?, ?, ?, ?)""",
            (snapshot_id, now, overall_health, len(file_health_scores), scope),
        )

        # Save per-file scores
        for fp, score in file_health_scores.items():
            comp_score = 0
            if complexity_data and fp in complexity_data:
                comp_score = complexity_data[fp].score if hasattr(complexity_data[fp], 'score') else 0
            role = "core"
            if role_data and fp in role_data:
                role = role_data[fp]

            conn.execute(
                """INSERT INTO file_snapshots
                   (snapshot_id, file_path, health_score, complexity_score, role)
                   VALUES (?, ?, ?, ?, ?)""",
                (snapshot_id, fp, score, comp_score, role),
            )

        conn.commit()
    except sqlite3.OperationalError:
        pass  # Table doesn't exist yet, skip gracefully
    finally:
        conn.close()


def get_previous_snapshot(db_path, scope=None):
    """
    Get the most recent snapshot before today for trend comparison.
    Returns dict with overall_health, timestamp, and file_scores mapping.
    """
    if not os.path.exists(db_path):
        return None

    _migrate_if_needed(db_path)
    today_start = _today_start_timestamp()

    conn = get_connection(db_path)
    try:
        # Get the most recent snapshot BEFORE today
        row = conn.execute(
            """SELECT snapshot_id, timestamp, overall_health, files_scored
               FROM health_snapshots
               WHERE timestamp < ? AND (scope IS ? OR scope = ?)
               ORDER BY timestamp DESC
               LIMIT 1""",
            (today_start, scope, scope),
        ).fetchone()

        if not row:
            return None

        snapshot_id = row["snapshot_id"]

        # Get per-file scores from that snapshot
        file_rows = conn.execute(
            """SELECT file_path, health_score, complexity_score, role
               FROM file_snapshots
               WHERE snapshot_id = ?""",
            (snapshot_id,),
        ).fetchall()

        file_scores = {r["file_path"]: r["health_score"] for r in file_rows}

        return {
            "snapshot_id": snapshot_id,
            "timestamp": row["timestamp"],
            "overall_health": row["overall_health"],
            "files_scored": row["files_scored"],
            "file_scores": file_scores,
        }
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def get_snapshot_history(db_path, scope=None, limit=10):
    """Get the last N snapshots for trend visualization."""
    if not os.path.exists(db_path):
        return []

    _migrate_if_needed(db_path)

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT snapshot_id, timestamp, overall_health, files_scored
               FROM health_snapshots
               WHERE scope IS ? OR scope = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (scope, scope, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _today_start_timestamp():
    """Get the Unix timestamp for the start of today (midnight local time)."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today.timestamp()


def _migrate_if_needed(db_path):
    """Run schema migration if the DB exists but has an older schema version."""
    if not os.path.exists(db_path):
        return
    try:
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'version'"
            ).fetchone()
            current_version = int(row["value"]) if row else 0

            if current_version < SCHEMA_VERSION:
                # Run full schema SQL — all statements use IF NOT EXISTS
                conn.executescript(SCHEMA_SQL)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                    ("version", str(SCHEMA_VERSION)),
                )
                conn.commit()
        finally:
            conn.close()
    except sqlite3.OperationalError:
        pass
