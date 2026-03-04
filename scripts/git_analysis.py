"""
Vitals — Git history analysis.

Extracts churn, co-change coupling, and knowledge distribution
from git log. Zero external dependencies.
"""

import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from itertools import combinations


def _run_git(repo_path, args, timeout=300):
    """Run a git command and return stdout lines."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return []
    if result.returncode != 0:
        return []
    return result.stdout.strip().splitlines() if result.stdout.strip() else []


def is_git_repo(path):
    """Check if path is inside a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def get_repo_root(path):
    """Get the root of the git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def get_repo_info(repo_path):
    """Get basic repo info: age, total commits, contributors."""
    # Total commits
    lines = _run_git(repo_path, ["rev-list", "--count", "HEAD"])
    total_commits = int(lines[0]) if lines else 0

    # First commit date
    lines = _run_git(repo_path, ["log", "--reverse", "--format=%aI", "-1"])
    first_commit = lines[0] if lines else None

    # Contributor count
    lines = _run_git(repo_path, ["shortlog", "-sn", "--no-merges", "HEAD"])
    contributors = len(lines)

    # Calculate repo age
    repo_age_days = 0
    if first_commit:
        try:
            first_date = datetime.fromisoformat(first_commit.replace("Z", "+00:00"))
            repo_age_days = (datetime.now(first_date.tzinfo) - first_date).days
        except (ValueError, TypeError):
            pass

    return {
        "total_commits": total_commits,
        "contributors": contributors,
        "repo_age_days": repo_age_days,
    }


def get_tracked_files(repo_path, scope_path=None):
    """Get list of tracked files, optionally scoped to a path."""
    args = ["ls-files"]
    if scope_path:
        args.append(scope_path)
    return _run_git(repo_path, args)


# ---------------------------------------------------------------------------
# Churn Analysis
# ---------------------------------------------------------------------------

def get_file_churn(repo_path, days=90, scope_path=None):
    """
    Get per-file churn metrics over the last N days.

    Returns dict: {file_path: {changes, lines_added, lines_removed, authors}}
    """
    since = f"--since={days}.days.ago"
    args = ["log", "--numstat", "--format=%H%x00%aI%x00%aN", "--no-merges", since]
    if scope_path:
        args += ["--", scope_path]

    lines = _run_git(repo_path, args)

    file_stats = defaultdict(lambda: {
        "changes": 0,
        "lines_added": 0,
        "lines_removed": 0,
        "authors": set(),
        "last_change": None,
    })

    current_author = None
    current_date = None

    for line in lines:
        if not line.strip():
            continue

        # Commit header line: hash\0date\0author
        if "\x00" in line:
            parts = line.split("\x00", 2)
            if len(parts) >= 3:
                current_date = parts[1]
                current_author = parts[2]
            continue

        # Numstat line: added\tremoved\tfile
        parts = line.split("\t")
        if len(parts) == 3:
            added_str, removed_str, file_path = parts
            # Skip binary files (shown as -)
            if added_str == "-" or removed_str == "-":
                continue
            try:
                added = int(added_str)
                removed = int(removed_str)
            except ValueError:
                continue

            stats = file_stats[file_path]
            stats["changes"] += 1
            stats["lines_added"] += added
            stats["lines_removed"] += removed
            if current_author:
                stats["authors"].add(current_author)
            if current_date and (stats["last_change"] is None or current_date > stats["last_change"]):
                stats["last_change"] = current_date

    # Convert author sets to counts
    result = {}
    for fp, stats in file_stats.items():
        result[fp] = {
            "changes": stats["changes"],
            "lines_added": stats["lines_added"],
            "lines_removed": stats["lines_removed"],
            "author_count": len(stats["authors"]),
            "last_change": stats["last_change"],
        }

    return result


# ---------------------------------------------------------------------------
# Co-Change Coupling
# ---------------------------------------------------------------------------

def get_co_change_coupling(repo_path, days=180, min_support=3, scope_path=None):
    """
    Find files that change together more often than expected.

    Groups commits by calendar day (logical change unit).
    Returns list of dicts: {file_a, file_b, co_changes, coupling_strength, total_a, total_b}
    """
    since = f"--since={days}.days.ago"
    args = ["log", "--name-only", "--format=%aI", "--no-merges", since]
    if scope_path:
        args += ["--", scope_path]

    lines = _run_git(repo_path, args)

    # Group files by day
    daily_changes = defaultdict(set)
    current_day = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Date line (ISO format)
        if line.startswith("20") and "T" in line:
            try:
                current_day = line[:10]  # YYYY-MM-DD
            except (ValueError, IndexError):
                pass
            continue

        # File name line
        if current_day:
            daily_changes[current_day].add(line)

    # Count individual file changes and co-changes
    file_changes = Counter()
    co_changes = Counter()

    for day, files in daily_changes.items():
        files = list(files)
        for f in files:
            file_changes[f] += 1
        # Only consider pairs if there are multiple files
        if 2 <= len(files) <= 50:  # Cap to avoid O(n^2) explosion
            for a, b in combinations(sorted(files), 2):
                co_changes[(a, b)] += 1

    # Compute coupling strength
    results = []
    for (a, b), count in co_changes.items():
        if count >= min_support:
            total_a = file_changes[a]
            total_b = file_changes[b]
            # Coupling strength = max directional probability
            strength = max(count / total_a, count / total_b) if min(total_a, total_b) > 0 else 0
            results.append({
                "file_a": a,
                "file_b": b,
                "co_changes": count,
                "coupling_strength": round(strength, 2),
                "total_a": total_a,
                "total_b": total_b,
            })

    return sorted(results, key=lambda x: x["coupling_strength"], reverse=True)


# ---------------------------------------------------------------------------
# Knowledge Distribution / Truck Factor
# ---------------------------------------------------------------------------

def get_knowledge_distribution(repo_path, files=None):
    """
    Get author distribution per file (for truck factor / knowledge risk).

    Returns dict: {file_path: {authors: [(name, commits)], truck_factor: int}}
    """
    if files is None:
        files = get_tracked_files(repo_path)

    result = {}

    # Scope to last 2 years and specific files to avoid scanning entire history
    args = [
        "log", "--format=%aN\t%H", "--no-merges", "--no-renames",
        "--since=2.years.ago", "--name-only", "--", *files
    ]
    lines = _run_git(repo_path, args)

    file_authors = defaultdict(Counter)
    current_author = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            # Author line: name\thash
            parts = line.split("\t", 1)
            current_author = parts[0]
            continue
        # File name
        if current_author:
            file_authors[line][current_author] += 1

    for fp in files:
        if fp in file_authors:
            authors = file_authors[fp]
            sorted_authors = sorted(authors.items(), key=lambda x: -x[1])
            total = sum(c for _, c in sorted_authors)

            # Truck factor: minimum authors needed to cover >50% of commits
            truck_factor = 0
            cumulative = 0
            for name, commits in sorted_authors:
                cumulative += commits
                truck_factor += 1
                if cumulative > total * 0.5:
                    break

            result[fp] = {
                "authors": sorted_authors[:5],  # Top 5
                "author_count": len(authors),
                "truck_factor": truck_factor,
                "total_commits": total,
            }
        else:
            result[fp] = {
                "authors": [],
                "author_count": 0,
                "truck_factor": 0,
                "total_commits": 0,
            }

    return result


# ---------------------------------------------------------------------------
# File Classification
# ---------------------------------------------------------------------------

def classify_file(file_path):
    """
    Classify a file's role: "test" or "core".

    Uses universal conventions — every programming ecosystem puts tests
    in directories named test/tests/spec and prefixes/suffixes test files
    with test_/Test/_test/_spec. This is structural, not language-specific.
    """
    parts = file_path.replace("\\", "/").split("/")
    name = parts[-1]
    stem = os.path.splitext(name)[0]
    lower_stem = stem.lower()

    # Directory signal: test/tests/spec in path
    for part in parts[:-1]:
        if part.lower() in ("test", "tests", "spec", "specs", "__tests__",
                             "testing", "fixtures"):
            return "test"

    # File name signals (flat checks, no nesting)
    if lower_stem.startswith("test_") or lower_stem.startswith("test-"):
        return "test"
    if lower_stem.endswith("_test") or lower_stem.endswith("-test"):
        return "test"
    if lower_stem.endswith("_spec") or lower_stem.endswith("-spec"):
        return "test"
    # CamelCase: FooTest.java, BarSpec.scala (check original case)
    if stem.endswith(("Test", "Tests", "Spec", "Specs")) and len(stem) > 4:
        return "test"

    return "core"


def compute_centrality(file_path, coupling_data):
    """
    Compute a file's centrality score from coupling data.

    Centrality = number of unique files this file co-changes with.
    Higher centrality = more files depend on or are affected by this file.
    A file that co-changes with 15 others has much higher blast radius
    than one that co-changes with 1.
    """
    count = 0
    for pair in coupling_data:
        if pair["file_a"] == file_path or pair["file_b"] == file_path:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Source File Filtering
# ---------------------------------------------------------------------------

def get_generated_files(repo_path, file_list=None):
    """
    Ask git which files are generated (linguist-generated attribute).

    This respects the repo's .gitattributes settings. Repos that mark
    *.lock, *.generated, etc. as linguist-generated will have those
    files filtered out automatically.

    Returns a set of file paths that are generated.
    """
    generated = set()

    # Batch query: pipe file list through git check-attr
    if file_list:
        # Use --stdin to check many files in one call
        try:
            input_text = "\n".join(file_list)
            result = subprocess.run(
                ["git", "check-attr", "linguist-generated", "--stdin"],
                cwd=repo_path,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    # Format: "path: linguist-generated: true"
                    if ": linguist-generated: true" in line or ": linguist-generated: set" in line:
                        path = line.split(": linguist-generated:")[0].strip()
                        generated.add(path)
        except (subprocess.TimeoutExpired, OSError):
            pass

    return generated


def is_source_file(file_path):
    """
    Check if a file is likely source code using structural signals.

    No hardcoded extension lists. Uses:
      - Must have a file extension
      - Not in hidden directories
      - Extension not too long (binary artifacts)
      - Not a lock file (machine-generated dependency manifests)
    """
    base = os.path.basename(file_path)
    _, ext = os.path.splitext(file_path)

    # No extension — likely not source code (Makefile, LICENSE, etc.)
    if not ext:
        return False

    # Skip files in hidden directories (convention across all ecosystems)
    parts = file_path.replace("\\", "/").split("/")
    for part in parts:
        if part.startswith(".") and part != ".":
            return False

    # Skip lock files — these are machine-generated dependency manifests,
    # not source code. This isn't a "language list" — it's filtering a
    # universal artifact type (like filtering .gitignore or .DS_Store).
    if ext == ".lock" or base.endswith(".lockfile"):
        return False

    # Skip obvious non-code by structural signal:
    # files with extensions longer than 5 chars are rarely source code
    if len(ext) > 6:
        return False

    return True


def filter_source_files(file_list, repo_path=None):
    """
    Filter a list of files to likely source code only.

    Two-pass filter:
    1. Structural: extension, hidden dirs, lock files
    2. Git-native: respect linguist-generated from .gitattributes
    """
    # Pass 1: structural filter
    candidates = [f for f in file_list if is_source_file(f)]

    # Pass 2: git-native generated file detection
    if repo_path and candidates:
        generated = get_generated_files(repo_path, candidates)
        if generated:
            candidates = [f for f in candidates if f not in generated]

    return candidates
