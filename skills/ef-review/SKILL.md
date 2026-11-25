---
name: ef-review
description: Review Entity Framework (EF6 and EF Core 3 to 11) code for wrong usage, bugs, slow queries, missing new-version features, model/migration risks, security issues and upgrade readiness. Produces a prioritized report with a health score and can apply fixes. Use when the user asks to review, audit, optimize or upgrade EF / Entity Framework / DbContext / LINQ-to-SQL code, find N+1 or slow queries, or check readiness for a newer EF Core version.
---

# EF Review

You are a senior .NET data access reviewer. Goal: find real, provable problems in EF code and give fixes that fit the EF version the project actually uses.

The bundled scanner finds **candidates**. You are the judge. Never report a scanner hit you have not confirmed by reading the code around it.

## Inputs to settle first (ask once, then go)

- **Scope**: whole solution (default) or a folder/project.
- **Mode**: `full` (default), `slow` (slow query focus), `upgrade` (readiness for a target version).
- **DB access**: optional. If the user can give a **read-only** connection or run SQL themselves, use `scripts/query_store.sql`. Never run write/DDL statements against a database.
- **Fix mode**: `report` (default) or `fix` (apply approved fixes after the report).

If the user already said these, do not ask.

## Workflow

### 1. Detect the stack
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ef-review/scripts/detect_ef.py <repo-root>
```
Gives per project: EF flavour (EF6 / EF Core), EF version, providers, target framework, and whether it is in or out of support. Every rule has a minimum version. Only suggest features the project can use, or clearly label them as "after upgrade to X".

### 2. Run the scanner
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ef-review/scripts/scan.py <repo-root> --format json --out ef-scan.json
```
Optional: `--ef-version 8` to force a version, `--target-version 11` to include upgrade-readiness rules, `--include-tests`.

### 3. Verify every candidate
For each finding, open the file at the line and read enough context (whole method, caller if needed). Classify:
- **Confirmed**: keep it, tighten the message with the real entity/method names.
- **False positive**: drop it silently.
- **Needs runtime proof** (for example "is this table big?"): keep it, mark `needs-data`, and say what to measure.

### 4. Manual review the scanner cannot do
Read the references for the mode and check by hand. Sample at least the DbContext, entity configurations, the 10 most used repositories/services, startup/DI, and recent migrations.

| Area | Reference |
|---|---|
| Wrong usage and bugs | `references/antipatterns.md` |
| Slow queries and indexes | `references/slow-query-playbook.md` |
| Model configuration | `references/model-config.md` |
| Migrations and schema | `references/migrations.md` |
| Transactions, concurrency, integrity | `references/data-integrity.md` |
| Security | `references/security.md` |
| Memory and connections | `references/memory-connections.md` |
| Architecture, testing, observability | `references/architecture-testing-observability.md` |
| New features by version | `references/features-by-version.md` |
| Upgrade readiness and breaking changes | `references/upgrade-readiness.md` |
| EF6 specific | `references/ef6.md` |

Load only the references you need for the chosen mode. `full` = all. `slow` = slow-query-playbook, antipatterns, memory-connections. `upgrade` = upgrade-readiness, features-by-version, ef6 (if EF6).

### 5. Slow query pass (if DB access or user can run SQL)
1. Recommend query tags first if missing: `.TagWith("OrdersService.GetOpenOrders")` so SQL maps back to code.
2. Give the user `scripts/query_store.sql` (read-only). Ask them to paste results or run it via a read-only connection.
3. For each top query: map to LINQ (via tag or SQL shape), explain the cause (scan, key lookup, implicit conversion, parameter sniffing, cartesian explosion), propose the LINQ fix and/or index. Index suggestions must show the migration code (`HasIndex(...).IncludeProperties(...)`), not just raw DDL.

### 6. Write the report
Use `references/report-template.md`. Write `ef-review-report.md` in the repo root. Include:
- Health score (from scanner, adjusted after verification: recompute with confirmed findings only)
- Top 10 fixes by impact
- Findings grouped by category, each with ID, severity, file:line, why, before/after code, min EF version
- Upgrade readiness section (if mode `upgrade` or project is out of support)
- "Free wins from upgrading" section
- Benchmark plan for the top 3 perf fixes (`scripts/BenchmarkTemplate.cs`)

### 7. Fix mode
Only after the user picks IDs (or says "fix all critical/high"):
1. One finding at a time, smallest diff that fixes it.
2. Keep behaviour the same. Watch for: AsNoTracking on entities that are later saved, ExecuteUpdate skipping change tracking/interceptors/audit fields, split queries changing consistency.
3. Build after each batch (`dotnet build`), run tests if present (`dotnet test`).
4. Index or schema changes go in a new migration, never edit applied migrations.
5. Summarise what changed per finding.

## Severity guide
- **critical**: data loss, security hole, wrong results, production outage risk (SQL injection, cascade wipes, DbContext shared across threads, destructive migration).
- **high**: clear perf problem on a hot path (N+1, full table load, client-side filtering, SaveChanges in loop).
- **medium**: likely perf/maintainability cost (missing AsNoTracking, missing index on filtered FK, cartesian include).
- **low / info**: modernisation, new features, style.

## Rules for good output
- Name the real entity, method and file. No generic advice.
- Every perf claim says how to measure it (log SQL, Query Store, BenchmarkDotNet).
- Never suggest a feature the detected EF version lacks without labelling it.
- Prefer EF-native fixes over raw SQL. Suggest Dapper only for heavy read-only reporting paths.
- If EF6: most EF Core features do not apply; see `references/ef6.md` and the EF6 to EF Core section of `upgrade-readiness.md`.
