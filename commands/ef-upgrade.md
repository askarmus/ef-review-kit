---
description: Check readiness to upgrade Entity Framework (EF6 to EF Core, or EF Core N to 10/11), list breaking changes that hit this codebase and new features to adopt
argument-hint: "[target-version e.g. 10 or 11] [path]"
---

Use the `ef-review` skill in **upgrade** mode.

Arguments: $ARGUMENTS. First number = target EF Core version (default 10, the LTS). Remaining = path (default repo root).

1. Run detect_ef.py, then `scan.py --target-version <N>`.
2. Read `references/upgrade-readiness.md` and `references/features-by-version.md` (and `ef6.md` for EF6 projects).
3. For every version being jumped over, check the breaking changes against this codebase and give file:line hits.
4. Write `ef-upgrade-report.md`: blockers, breaking changes found, step-by-step plan, new features worth adopting after upgrade, free wins.
