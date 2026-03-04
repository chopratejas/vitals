# Roadmap

## Released

### v0.1 — Health Scoring & Provenance Capture

- [x] Per-file health scores (1-10) combining churn, complexity, coupling, knowledge
- [x] Hotspot detection ranked by ROI (churn x complexity x centrality x role)
- [x] Co-change coupling detection from git history
- [x] Knowledge risk / bus factor analysis
- [x] ROI-aware ranking (core > test, central > leaf)
- [x] Silent AI provenance capture via PostToolUse hooks
- [x] Zero external dependencies
- [x] Monorepo-safe filtering (lock files, configs, generated code excluded)
- [x] Graceful degradation without git

### v0.2 — Trend Tracking

- [x] Health snapshots saved after each scan (once per calendar day)
- [x] Trend comparison showing degrading/improving files with deltas
- [x] Overall health trajectory
- [x] Schema migration (v1 databases auto-upgrade)
- [x] Marketplace distribution support

## Planned

### v0.3 — Drift Detection

- [ ] Intent fingerprinting using code embeddings
- [ ] Semantic drift measurement (original intent vs. current implementation)
- [ ] `/vitals:drift` command to compare original purpose vs. current state
- [ ] Drift score per file (0-100)

### v0.4 — Decay Prediction

- [ ] Per-module decay curves (exponential fit on health history)
- [ ] Estimated liability dates ("this file becomes unmaintainable in ~47 days")
- [ ] ROI-ranked refactoring plans with specific, actionable steps
- [ ] Confidence scores on predictions

### v1.0 — SaaS Dashboard

- [ ] Team-level health views
- [ ] Cross-repo decay comparison
- [ ] Organizational technical debt portfolio
- [ ] Benchmark data ("how does your team compare?")
- [ ] CI/CD quality gates via MCP server

## Contributing

Vitals is MIT licensed. Before contributing:

- Keep the zero-dependency constraint (Python stdlib only)
- No regex for file classification (structural signals only)
- Test against a real repo with 100+ files
- The report command must remain read-only (no side effects)
