---
description: Find slow Entity Framework queries (static scan + optional SQL Server Query Store analysis) and suggest LINQ and index fixes
argument-hint: "[path]"
---

Use the `ef-review` skill in **slow** mode.

Target: $ARGUMENTS (if empty, use the current repo root).

1. Run detect_ef.py and scan.py. Keep only performance findings (EF001-EF018, EF5xx, EF101/EF102 if relevant).
2. Check whether queries are tagged and whether slow query logging exists. If not, propose the TagWith + SlowQueryInterceptor setup.
3. Ask me if I can run `scripts/query_store.sql` (read-only) and paste the results. If yes, map the top queries back to code and propose fixes plus indexes as EF model config.
4. Write `ef-slow-query-report.md` with ranked fixes and a benchmark plan for the top 3.
