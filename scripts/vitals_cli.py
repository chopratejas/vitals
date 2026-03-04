#!/usr/bin/env python3
"""
Vitals CLI — Codebase health analysis.

Usage:
    python3 vitals_cli.py report [path] [--top N]
    python3 vitals_cli.py version

Works standalone or invoked by the /vitals:scan Claude Code skill.
"""

import argparse
import json
import os
import sys

# Add scripts dir to path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import git_analysis
import complexity
import health_score
import report
import db


TOOL_NAME = "Vitals"
VERSION = "0.1.0"


def find_repo_root(start_path=None):
    """Find the git repository root. Returns None if not in a git repo."""
    if start_path:
        start = os.path.abspath(start_path)
        if not os.path.exists(start):
            start = os.getcwd()
    else:
        start = os.getcwd()

    return git_analysis.get_repo_root(start)


def _walk_source_files(directory, scope_path=None):
    """Walk a directory tree and return source files (non-git fallback)."""
    target = os.path.join(directory, scope_path) if scope_path else directory
    if not os.path.isdir(target):
        target = directory

    results = []
    for root, dirs, files in os.walk(target):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, directory)
            if git_analysis.is_source_file(rel):
                results.append(rel)
    return results


def run_report(args):
    """Run the full health report."""
    repo_root = find_repo_root(args.path)
    has_git = repo_root is not None
    scope_path = None

    # Determine the analysis root directory
    if has_git:
        analysis_root = repo_root
    else:
        analysis_root = os.path.abspath(args.path) if args.path else os.getcwd()
        if not os.path.isdir(analysis_root):
            analysis_root = os.getcwd()

    if args.path:
        abs_path = os.path.abspath(args.path)
        if os.path.exists(abs_path):
            scope_path = os.path.relpath(abs_path, analysis_root)
        else:
            scope_path = args.path
        if scope_path == ".":
            scope_path = None

    top_n = args.top

    # --- Gather data ---
    #
    # Two modes:
    #   WITH GIT: full analysis (churn, coupling, knowledge, complexity)
    #   NO GIT:   complexity-only scan (still valuable — finds the most
    #             structurally complex files even without history)

    repo_info = {}
    churn_data = {}
    coupling_data = []
    knowledge_data = {}

    if has_git:
        repo_info = git_analysis.get_repo_info(analysis_root)

        # Churn analysis (90 days)
        churn_data = git_analysis.get_file_churn(analysis_root, days=90, scope_path=scope_path)

        # Filter churn to source files BEFORE complexity analysis
        churning_files = [f for f in churn_data.keys()
                          if churn_data[f].get("changes", 0) >= 2]
        source_churning = git_analysis.filter_source_files(churning_files, analysis_root)

        # Compute complexity only for source files that are churning
        complexity_data = complexity.compute_complexity_batch(source_churning, analysis_root)

        # Keep only files with structural complexity (nesting gate)
        code_files = [f for f in source_churning
                      if complexity_data.get(f) and complexity_data[f].score > 0]

        # All tracked source files for stats
        all_files = git_analysis.get_tracked_files(analysis_root, scope_path)
        source_files = git_analysis.filter_source_files(all_files, analysis_root)

        # Co-change coupling — filtered to source files
        raw_coupling = git_analysis.get_co_change_coupling(
            analysis_root, days=180, min_support=2, scope_path=scope_path
        )
        coupling_data = [
            cp for cp in raw_coupling
            if git_analysis.is_source_file(cp["file_a"])
            and git_analysis.is_source_file(cp["file_b"])
        ]

        # Knowledge distribution
        knowledge_files = code_files[:50] if code_files else source_files[:50]
        knowledge_data = git_analysis.get_knowledge_distribution(analysis_root, knowledge_files)
    else:
        # No git — complexity-only scan
        source_files = _walk_source_files(analysis_root, scope_path)
        complexity_data = complexity.compute_complexity_batch(source_files, analysis_root)
        code_files = [f for f in source_files
                      if complexity_data.get(f) and complexity_data[f].score > 0]

    if not code_files and not source_files:
        print(report.format_error(
            "No source files found. Check that the path contains code files."
        ))
        sys.exit(1)

    # AI provenance data
    db_path = db.get_db_path(analysis_root)
    provenance_info = None
    ai_file_stats = []

    if db.has_provenance_data(db_path):
        summary = db.get_provenance_summary(db_path)
        ai_file_stats = db.get_ai_file_stats(db_path, days=30)
        provenance_info = {
            "has_data": True,
            "summary": summary,
            "ai_files": ai_file_stats,
        }
    else:
        # Don't create .vitals/ or init DB on read-only report.
        # The DB is created by the provenance capture hook on first edit.
        provenance_info = {"has_data": False}

    # --- Compute health scores (only for real code files) ---

    coupling_lookup = {}
    for cp in coupling_data:
        for f in [cp["file_a"], cp["file_b"]]:
            if f not in coupling_lookup or cp["coupling_strength"] > coupling_lookup[f]:
                coupling_lookup[f] = cp["coupling_strength"]

    ai_lookup = {}
    if ai_file_stats:
        for af in ai_file_stats:
            fp = af["file_path"]
            ai_changes = af["edit_count"] + af["write_count"]
            total = churn_data.get(fp, {}).get("changes", ai_changes)
            ai_lookup[fp] = min(1.0, ai_changes / max(1, total))

    file_health_scores = {}
    for fp in code_files:
        score = health_score.compute_file_health(
            churn_data=churn_data.get(fp),
            complexity_result=complexity_data.get(fp),
            coupling_strength=coupling_lookup.get(fp, 0.0),
            knowledge_data=knowledge_data.get(fp),
            ai_ratio=ai_lookup.get(fp, 0.0),
        )
        file_health_scores[fp] = score

    overall = health_score.compute_codebase_health(file_health_scores)

    # --- Build hotspots (all files here are already real code) ---
    #
    # ROI-aware ranking: core production code with high centrality
    # is prioritized over tests and leaf utilities.
    #
    # risk = (10 - health) × churn × role_weight × centrality_boost
    #   role_weight: core=1.0, test=0.3 (tests matter less for ROI)
    #   centrality_boost: 1 + (coupling_partners × 0.2)

    ROLE_WEIGHTS = {"core": 1.0, "test": 0.3}

    hotspots = []
    for fp in code_files:
        h = file_health_scores.get(fp, 10.0)
        churn = churn_data.get(fp, {})
        comp = complexity_data.get(fp)
        changes = churn.get("changes", 0)

        role = git_analysis.classify_file(fp)
        centrality = git_analysis.compute_centrality(fp, coupling_data)
        role_weight = ROLE_WEIGHTS.get(role, 1.0)
        centrality_boost = 1.0 + (centrality * 0.2)

        risk = (10.0 - h) * changes * role_weight * centrality_boost

        hotspots.append({
            "file_path": fp,
            "health": h,
            "role": role,
            "centrality": centrality,
            "churn_data": churn,
            "churn_label": health_score.classify_churn(changes),
            "complexity_score": comp.score if comp else 0,
            "coupling_strength": coupling_lookup.get(fp, 0.0),
            "changes": changes,
            "risk_score": round(risk, 1),
        })

    hotspots.sort(key=lambda x: x["risk_score"], reverse=True)
    hotspots = hotspots[:top_n]

    # --- Build knowledge risk list ---

    knowledge_risk = []
    for fp, kd in knowledge_data.items():
        if kd["truck_factor"] <= 1 and kd["author_count"] > 0:
            knowledge_risk.append({
                "file_path": fp,
                "truck_factor": kd["truck_factor"],
                "author_count": kd["author_count"],
                "authors": kd["authors"],
            })
    # Sort by truck factor (ascending), then by total commits (descending)
    knowledge_risk.sort(key=lambda x: (x["truck_factor"], -len(x.get("authors", []))))

    # --- Format and output ---

    analysis = {
        "mode": "full" if has_git else "complexity-only",
        "repo_info": repo_info,
        "file_health": file_health_scores,
        "hotspots": hotspots,
        "coupling": coupling_data[:5],  # Top 5 coupling pairs
        "knowledge_risk": knowledge_risk,
        "provenance": provenance_info,
        "overall_health": overall,
        "files_analyzed": len(source_files),
        "scope": scope_path,
    }

    if getattr(args, "json", False):
        # Structured JSON output for Claude to reason about
        print(json.dumps(analysis, indent=2, default=str))
    else:
        # Human-readable terminal report for standalone use
        print(report.format_health_report(analysis))


def main():
    parser = argparse.ArgumentParser(
        description="Vitals — Codebase health analysis"
    )
    subparsers = parser.add_subparsers(dest="command")

    # report command
    report_parser = subparsers.add_parser("report", help="Generate health report")
    report_parser.add_argument("path", nargs="?", default=None,
                               help="Scope analysis to a path")
    report_parser.add_argument("--top", type=int, default=10,
                               help="Number of hotspots to show (default: 10)")
    report_parser.add_argument("--json", action="store_true",
                               help="Output structured JSON for Claude analysis")

    # version command
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "version":
        print(f"{TOOL_NAME} v{VERSION}")
    elif args.command == "report":
        run_report(args)
    else:
        # Default to report if no command given
        args.path = None
        args.top = 10
        args.json = False
        run_report(args)


if __name__ == "__main__":
    main()
