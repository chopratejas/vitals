# Health Scores

Every file gets a health score from **1.0** (critical) to **10.0** (excellent).

## Score Categories

| Score | Category | What It Means | Action |
|-------|----------|---------------|--------|
| **9-10** | Healthy | Well-structured, low risk | Monitor |
| **7-9** | Good | Minor issues, stable | Watch |
| **4-7** | Warning | Accumulating debt | Plan refactoring |
| **1-4** | Alert | High defect risk | Fix now |

!!! warning "Alert Zone"
    Research shows files with health scores below 4 contain **15x more defects** than healthy files. These are your highest-priority targets.

## What Goes Into the Score

The health score combines four signals, each scored 1-10 and weighted:

| Signal | Weight | Source | What It Measures |
|--------|--------|--------|-----------------|
| **Complexity** | 30% | Indentation depth + AST (Python) | How deeply nested and structurally dense the code is |
| **Churn** | 30% | `git log` (last 90 days) | How frequently the file changes |
| **Coupling** | 20% | Co-change analysis (last 180 days) | How tightly bound to other files |
| **Knowledge** | 20% | `git shortlog` (last 2 years) | How concentrated the knowledge is (truck factor) |

## Complexity Scoring

Complexity is measured by **indentation depth**, not language-specific keywords.

- **Python files**: AST-based analysis (precise function/branch/nesting detection)
- **All other languages**: Indentation-based (measures nesting from whitespace)

The nesting gate filters non-code: files with max nesting depth <= 2 (lock files, configs, prose, data) score zero and are excluded from analysis entirely.

### Why Indentation?

CodeScene's research validates that nesting depth is the **strongest single predictor** of defect density. We don't need to know what creates the nesting (if/for/while) — we just measure that it exists. This works for every language without maintaining keyword lists.

## Churn Scoring

| Changes in 90 days | Churn Level | Sub-Score |
|---------------------|-------------|-----------|
| 0-2 | LOW | 10.0 |
| 3-5 | LOW-MED | 8.5 |
| 6-10 | MED | 7.0 |
| 11-15 | MED-HIGH | 5.0 |
| 16-25 | HIGH | 3.5 |
| 26+ | VERY HIGH | 2.0 |

## Coupling Scoring

Coupling strength is the probability that file B changes when file A changes:

```
LiCh(A→B) = co_changes(A,B) / changes(A)
```

| Coupling Strength | Sub-Score |
|-------------------|-----------|
| 0-20% | 10.0 |
| 20-40% | 8.0 |
| 40-60% | 6.0 |
| 60-80% | 4.0 |
| 80-100% | 2.0 |

## Knowledge Scoring (Truck Factor)

The truck factor is the minimum number of authors who need to leave before knowledge of a file is lost (covers >50% of commits).

| Truck Factor | Sub-Score |
|--------------|-----------|
| 3+ authors | 10.0 |
| 2 authors | 7.5 |
| 1 author (multi-contributor file) | 5.0 |
| 1 author (sole contributor) | 3.0 |

## Overall Codebase Health

The codebase health is a **weighted average** where unhealthy files count more:

```
weight(file) = 11 - health_score
```

A file with score 2 has weight 9. A file with score 9 has weight 2. This means a few critically unhealthy hotspots drag down the overall score, reflecting the reality that a codebase is only as healthy as its worst hotspots.
