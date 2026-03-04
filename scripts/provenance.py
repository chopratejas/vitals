#!/usr/bin/env python3
"""
Vitals — Provenance capture for Claude Code hooks.

Called by PostToolUse (async) and SessionEnd hooks.
Reads JSON from stdin and writes to .vitals/store.db.

Usage:
    echo '{"session_id": "...", ...}' | python3 provenance.py capture
    echo '{"session_id": "...", ...}' | python3 provenance.py aggregate
"""

import json
import os
import sys
import time
import uuid

# Add scripts dir to path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db


def find_repo_root(start_path):
    """Walk up to find .git directory."""
    path = os.path.abspath(start_path)
    while path != os.path.dirname(path):
        if os.path.isdir(os.path.join(path, ".git")):
            return path
        path = os.path.dirname(path)
    return None


def estimate_lines_changed(tool_name, tool_input):
    """Estimate lines changed from tool input."""
    if tool_name == "Edit":
        old_str = tool_input.get("old_string", tool_input.get("old_str", ""))
        new_str = tool_input.get("new_string", tool_input.get("new_str", ""))
        old_lines = len(old_str.splitlines()) if old_str else 0
        new_lines = len(new_str.splitlines()) if new_str else 0
        return abs(new_lines - old_lines) + max(old_lines, new_lines)
    elif tool_name == "Write":
        content = tool_input.get("content", tool_input.get("file_content", ""))
        return len(content.splitlines()) if content else 0
    return 0


def make_relative(file_path, repo_root):
    """Convert absolute path to repo-relative path."""
    try:
        return os.path.relpath(file_path, repo_root)
    except ValueError:
        return file_path


def capture(hook_data):
    """Handle PostToolUse hook — capture a provenance event."""
    cwd = hook_data.get("cwd", os.getcwd())
    repo_root = find_repo_root(cwd)
    if not repo_root:
        return  # Not in a git repo, skip silently

    db_path = db.ensure_db_dir(repo_root)
    db.init_db(db_path)

    session_id = hook_data.get("session_id", "unknown")
    tool_name = hook_data.get("tool_name", "unknown")
    tool_input = hook_data.get("tool_input", {})

    # Extract file path from tool input
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return  # No file path, skip

    rel_path = make_relative(file_path, repo_root)
    lines_changed = estimate_lines_changed(tool_name, tool_input)

    event_id = str(uuid.uuid4())
    timestamp = time.time()

    db.insert_provenance_event(
        db_path=db_path,
        event_id=event_id,
        session_id=session_id,
        timestamp=timestamp,
        file_path=rel_path,
        tool_name=tool_name,
        lines_changed=lines_changed,
    )


def aggregate(hook_data):
    """Handle SessionEnd hook — aggregate session provenance."""
    cwd = hook_data.get("cwd", os.getcwd())
    repo_root = find_repo_root(cwd)
    if not repo_root:
        return

    db_path = db.get_db_path(repo_root)
    if not os.path.exists(db_path):
        return

    session_id = hook_data.get("session_id", "unknown")

    conn = db.get_connection(db_path)
    try:
        row = conn.execute(
            """SELECT
                 COUNT(DISTINCT file_path) as files_touched,
                 SUM(CASE WHEN tool_name = 'Edit' THEN 1 ELSE 0 END) as total_edits,
                 SUM(CASE WHEN tool_name = 'Write' THEN 1 ELSE 0 END) as total_writes
               FROM provenance_events
               WHERE session_id = ?""",
            (session_id,),
        ).fetchone()

        files_touched = row["files_touched"] or 0 if row else 0
        total_edits = row["total_edits"] or 0 if row else 0
        total_writes = row["total_writes"] or 0 if row else 0

        if total_edits > 0 or total_writes > 0:
            db.upsert_session_summary(
                db_path=db_path,
                session_id=session_id,
                files_touched=files_touched,
                total_edits=total_edits,
                total_writes=total_writes,
            )
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: provenance.py [capture|aggregate]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    # Read hook JSON from stdin
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_data = {}

    if command == "capture":
        capture(hook_data)
    elif command == "aggregate":
        aggregate(hook_data)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
