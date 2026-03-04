"""
Vitals — SQLite database operations.
Stores AI provenance events and session summaries.
Zero external dependencies (uses Python's built-in sqlite3).
"""

import os
import sqlite3
import time

SCHEMA_VERSION = 1

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
