"""
Vitals — Composite health scoring.

Combines churn, complexity, coupling, and knowledge signals
into a single 1-10 health score per file.
"""


def compute_file_health(churn_data, complexity_result, coupling_strength,
                        knowledge_data, ai_ratio=0.0):
    """
    Compute a file's health score on a 1-10 scale.

    1 = critical (CodeScene "alert" territory: 15x more defects)
    4 = warning threshold
    9+ = healthy

    Inputs:
        churn_data: dict with {changes, lines_added, lines_removed}
        complexity_result: ComplexityResult instance
        coupling_strength: float 0-1 (max coupling with any other file)
        knowledge_data: dict with {truck_factor, author_count}
        ai_ratio: float 0-1 (proportion of recent changes that are AI-generated)
    """
    # --- Sub-scores (each 1-10, higher = healthier) ---

    # Complexity sub-score
    raw_complexity = complexity_result.score if complexity_result else 0
    if raw_complexity <= 10:
        complexity_score = 10.0
    elif raw_complexity <= 20:
        complexity_score = 8.5
    elif raw_complexity <= 35:
        complexity_score = 7.0
    elif raw_complexity <= 50:
        complexity_score = 5.5
    elif raw_complexity <= 65:
        complexity_score = 4.0
    elif raw_complexity <= 80:
        complexity_score = 2.5
    else:
        complexity_score = 1.0

    # Churn sub-score
    changes = churn_data.get("changes", 0) if churn_data else 0
    if changes <= 2:
        churn_score = 10.0
    elif changes <= 5:
        churn_score = 8.5
    elif changes <= 10:
        churn_score = 7.0
    elif changes <= 15:
        churn_score = 5.0
    elif changes <= 25:
        churn_score = 3.5
    else:
        churn_score = 2.0

    # Coupling sub-score
    if coupling_strength <= 0.2:
        coupling_score = 10.0
    elif coupling_strength <= 0.4:
        coupling_score = 8.0
    elif coupling_strength <= 0.6:
        coupling_score = 6.0
    elif coupling_strength <= 0.8:
        coupling_score = 4.0
    else:
        coupling_score = 2.0

    # Knowledge sub-score (truck factor)
    truck_factor = knowledge_data.get("truck_factor", 0) if knowledge_data else 0
    author_count = knowledge_data.get("author_count", 0) if knowledge_data else 0

    if truck_factor == 0 and author_count == 0:
        knowledge_score = 5.0  # Unknown, neutral
    elif truck_factor >= 3:
        knowledge_score = 10.0
    elif truck_factor == 2:
        knowledge_score = 7.5
    elif truck_factor == 1 and author_count >= 2:
        knowledge_score = 5.0
    elif truck_factor == 1:
        knowledge_score = 3.0
    else:
        knowledge_score = 5.0

    # --- Weighted combination ---
    health = (
        0.30 * complexity_score +
        0.30 * churn_score +
        0.20 * coupling_score +
        0.20 * knowledge_score
    )

    # AI ratio penalty: files with high AI generation AND high churn
    # are at higher risk (they're being regenerated frequently)
    if ai_ratio > 0.5 and changes > 5:
        ai_penalty = ai_ratio * 0.5  # Up to 0.5 point penalty
        health = max(1.0, health - ai_penalty)

    return round(max(1.0, min(10.0, health)), 1)


def compute_codebase_health(file_health_scores):
    """
    Compute overall codebase health from individual file scores.

    Uses a weighted average where unhealthy files count more
    (because a few unhealthy hotspots drag down the whole codebase).
    """
    if not file_health_scores:
        return 10.0

    scores = list(file_health_scores.values())

    # Weight: unhealthy files get higher weight
    # A file with score 2 has weight 5x a file with score 10
    total_weight = 0
    weighted_sum = 0

    for score in scores:
        weight = max(1.0, 11.0 - score)  # score=1 -> weight=10, score=10 -> weight=1
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return 10.0

    return round(weighted_sum / total_weight, 1)


def classify_health(score):
    """Classify a health score into a category."""
    if score >= 9.0:
        return "HEALTHY"
    elif score >= 7.0:
        return "GOOD"
    elif score >= 4.0:
        return "WARNING"
    else:
        return "ALERT"


def classify_churn(changes):
    """Classify churn rate."""
    if changes <= 2:
        return "LOW"
    elif changes <= 8:
        return "MED"
    else:
        return "HIGH"
