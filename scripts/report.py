"""
Vitals — Terminal report formatting.

Produces beautiful, readable health reports with Unicode tables
and ANSI color support.
"""

import os
import sys
import time

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"

# Check if terminal supports color
USE_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
if os.environ.get("NO_COLOR"):
    USE_COLOR = False


def c(text, color):
    """Apply ANSI color if terminal supports it."""
    if USE_COLOR:
        return f"{color}{text}{RESET}"
    return text


def health_color(score):
    """Get color for a health score."""
    if score >= 9.0:
        return GREEN
    elif score >= 7.0:
        return CYAN
    elif score >= 4.0:
        return YELLOW
    else:
        return RED


def health_bar(score, width=20):
    """Create a visual health bar."""
    filled = int(score / 10.0 * width)
    empty = width - filled
    color = health_color(score)
    bar = c("█" * filled, color) + c("░" * empty, DIM)
    return bar


def format_health_report(analysis):
    """
    Format the full health report.

    analysis: dict with keys:
        - repo_info: {total_commits, contributors, repo_age_days}
        - file_health: {file_path: score}
        - hotspots: [{file_path, health, churn_data, complexity, coupling_strength}]
        - coupling: [{file_a, file_b, co_changes, coupling_strength}]
        - knowledge_risk: [{file_path, truck_factor, author_count, authors}]
        - provenance: {has_data, summary, ai_files} or None
        - overall_health: float
        - files_analyzed: int
        - scope: str or None
    """
    lines = []

    # Header
    lines.append("")
    lines.append(c("Vitals v0.1.0 — Codebase Health Report", BOLD))
    lines.append(c("═" * 50, DIM))
    lines.append("")

    # Overall health
    overall = analysis.get("overall_health", 10.0)
    files_analyzed = analysis.get("files_analyzed", 0)
    repo_info = analysis.get("repo_info", {})

    health_label = c(f"{overall:.1f} / 10.0", BOLD + health_color(overall))
    lines.append(f"  Overall Health: {health_label}  {health_bar(overall)}")
    lines.append("")

    # Meta info
    meta_parts = [f"Files Analyzed: {files_analyzed}"]
    age_days = repo_info.get("repo_age_days", 0)
    if age_days > 365:
        meta_parts.append(f"Git History: {age_days // 365}y {(age_days % 365) // 30}m")
    elif age_days > 30:
        meta_parts.append(f"Git History: {age_days // 30} months")
    elif age_days > 0:
        meta_parts.append(f"Git History: {age_days} days")
    contributors = repo_info.get("contributors", 0)
    if contributors > 0:
        meta_parts.append(f"Contributors: {contributors}")

    lines.append(c("  " + "  |  ".join(meta_parts), DIM))
    lines.append("")

    # Hotspots
    hotspots = analysis.get("hotspots", [])
    if hotspots:
        lines.append(_format_hotspots(hotspots))
        lines.append("")

    # Coupling
    coupling = analysis.get("coupling", [])
    if coupling:
        lines.append(_format_coupling(coupling))
        lines.append("")

    # Knowledge risk
    knowledge = analysis.get("knowledge_risk", [])
    if knowledge:
        lines.append(_format_knowledge_risk(knowledge))
        lines.append("")

    # AI Provenance
    provenance = analysis.get("provenance")
    lines.append(_format_provenance(provenance))
    lines.append("")

    # Top recommendation
    if hotspots:
        lines.append(_format_recommendation(hotspots, coupling, knowledge))
        lines.append("")

    return "\n".join(lines)


def _format_hotspots(hotspots):
    """Format the hotspots table."""
    lines = []
    lines.append(c("  HOTSPOTS — Ranked by ROI (core > test, central > leaf)", BOLD + RED))
    lines.append("")

    # Calculate column widths
    max_path = max(len(_truncate_path(h["file_path"])) for h in hotspots)
    max_path = max(max_path, 4)
    max_path = min(max_path, 40)

    # Header
    header = (
        f"  {'File':<{max_path}}  "
        f"{'Health':>6}  "
        f"{'Role':>4}  "
        f"{'Complexity':>4}  "
        f"{'Churn':>7}  "
        f"{'Links':>5}"
    )
    lines.append(c(header, DIM))
    lines.append(c("  " + "─" * (max_path + 36), DIM))

    for h in hotspots:
        path = _truncate_path(h["file_path"], max_path)
        health = h["health"]
        role = h.get("role", "core")
        comp = h.get("complexity_score", 0)
        changes = h.get("changes", 0)
        centrality = h.get("centrality", 0)

        health_str = c(f"{health:>5.1f}", health_color(health))

        if role == "test":
            role_str = c("test", DIM)
        else:
            role_str = c("core", CYAN)

        comp_str = c(f"{comp:>4}", RED if comp > 50 else (YELLOW if comp > 30 else DIM))
        churn_str = f"{changes:>3}/90d"
        links_str = c(f"{centrality:>5}", MAGENTA) if centrality > 0 else c(f"{centrality:>5}", DIM)

        lines.append(
            f"  {path:<{max_path}}  "
            f"{health_str}  "
            f"{role_str}  "
            f"{comp_str}  "
            f"{churn_str}  "
            f"{links_str}"
        )

    return "\n".join(lines)


def _format_coupling(coupling_pairs):
    """Format co-change coupling section."""
    lines = []
    lines.append(c("  COUPLING — Files That Change Together", BOLD + MAGENTA))
    lines.append("")

    for pair in coupling_pairs[:5]:  # Top 5
        a = _truncate_path(pair["file_a"], 35)
        b = _truncate_path(pair["file_b"], 35)
        strength = pair["coupling_strength"]
        co_changes = pair["co_changes"]

        strength_pct = f"{strength * 100:.0f}%"
        color = RED if strength > 0.7 else (YELLOW if strength > 0.5 else DIM)
        lines.append(
            f"  {a} {c('<>', MAGENTA)} {b}  "
            f"{c(strength_pct, color)} coupling ({co_changes} co-changes)"
        )

    return "\n".join(lines)


def _format_knowledge_risk(knowledge_items):
    """Format knowledge risk / bus factor section."""
    lines = []
    lines.append(c("  KNOWLEDGE RISK — Bus Factor", BOLD + YELLOW))
    lines.append("")

    for item in knowledge_items[:5]:  # Top 5 riskiest
        path = _truncate_path(item["file_path"], 35)
        truck = item["truck_factor"]
        authors = item["author_count"]

        if truck <= 1 and authors <= 1:
            risk = c("HIGH RISK", RED)
            detail = "1 contributor"
        elif truck <= 1:
            risk = c("MODERATE", YELLOW)
            detail = f"{authors} contributors, dominated by 1"
        else:
            risk = c(f"truck factor: {truck}", DIM)
            detail = f"{authors} contributors"

        lines.append(f"  {path:<35}  — {detail} ({risk})")

    return "\n".join(lines)


def _format_provenance(provenance):
    """Format AI provenance section."""
    lines = []

    if provenance and provenance.get("has_data"):
        summary = provenance["summary"]
        ai_files = provenance.get("ai_files", [])

        total_events = summary.get("total_events", 0)
        unique_files = summary.get("unique_files", 0)
        sessions = summary.get("total_sessions", 0)

        first_event = summary.get("first_event")
        if first_event:
            days_tracking = max(1, int((time.time() - first_event) / 86400))
            tracking_label = f"{days_tracking} day{'s' if days_tracking != 1 else ''}"
        else:
            tracking_label = "recently"

        lines.append(c("  AI PROVENANCE — Code Generation Tracking", BOLD + CYAN))
        lines.append("")
        lines.append(
            f"  Tracking for {tracking_label}: "
            f"{total_events} AI edits across {unique_files} files in {sessions} sessions"
        )

        if ai_files:
            lines.append("")
            lines.append(c("  Most AI-modified files:", DIM))
            for af in ai_files[:5]:
                fp = _truncate_path(af["file_path"], 35)
                edits = af.get("edit_count", 0)
                writes = af.get("write_count", 0)
                total = edits + writes
                lines.append(f"    {fp:<35}  {total} AI changes ({edits} edits, {writes} writes)")
    else:
        lines.append(c("  AI PROVENANCE — Tracking Active", BOLD + CYAN))
        lines.append("")
        lines.append(
            c("  Provenance capture started. After a few coding sessions,", DIM)
        )
        lines.append(
            c("  run /vitals:scan again for AI-generated code insights.", DIM)
        )

    return "\n".join(lines)


def _format_recommendation(hotspots, coupling, knowledge):
    """Generate a top recommendation based on the analysis."""
    lines = []
    lines.append(c("  TOP RECOMMENDATION", BOLD + GREEN))
    lines.append("")

    if not hotspots:
        lines.append(c("  Codebase looks healthy! Keep up the good work.", GREEN))
        return "\n".join(lines)

    worst = hotspots[0]
    path = worst["file_path"]
    health = worst["health"]
    changes = worst.get("changes", 0)
    complexity = worst.get("complexity_score", 0)

    reasons = []
    if changes > 5:
        reasons.append(f"high churn ({changes} changes in 90 days)")
    if complexity > 30:
        reasons.append(f"high complexity ({complexity})")

    # Check if it has knowledge risk
    for k in knowledge:
        if k["file_path"] == path and k["truck_factor"] <= 1:
            reasons.append("single contributor")
            break

    # Check if it has coupling
    for cp in coupling:
        if cp["file_a"] == path or cp["file_b"] == path:
            other = cp["file_b"] if cp["file_a"] == path else cp["file_a"]
            if cp["coupling_strength"] > 0.5:
                reasons.append(f"strongly coupled to {_truncate_path(other, 30)}")
            break

    reason_str = ", ".join(reasons) if reasons else "multiple risk factors"

    lines.append(
        f"  {c(path, BOLD)} is your #1 priority: {reason_str}."
    )

    if health < 4.0:
        lines.append(
            f"  Health score {c(f'{health:.1f}', RED)} is in the alert zone "
            f"(files in this range have 15x more defects)."
        )
    elif health < 7.0:
        lines.append(
            f"  Health score {c(f'{health:.1f}', YELLOW)} is in the warning zone."
        )

    if complexity > 40:
        lines.append(
            "  Consider breaking large functions into smaller units and reducing nesting depth."
        )

    return "\n".join(lines)


def _truncate_path(path, max_len=40):
    """Truncate a file path intelligently, keeping the end."""
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3):]


def format_error(message):
    """Format an error message."""
    return c(f"\n  Error: {message}\n", RED)
