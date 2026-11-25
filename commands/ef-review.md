---
description: Full Entity Framework review (bugs, slow queries, model, migrations, security, new features) with health score
argument-hint: "[path] [--fix]"
---

Use the `ef-review` skill in **full** mode.

Target: $ARGUMENTS (if empty, use the current repo root).

1. Run detect_ef.py and scan.py from the skill's scripts folder.
2. Verify every candidate by reading the code. Drop false positives.
3. Do the manual review using all reference files.
4. Write `ef-review-report.md` using the report template, then show me the summary and the top 10 fixes.
5. If `--fix` was passed, ask which IDs to fix, then apply them one by one, building after each batch.
