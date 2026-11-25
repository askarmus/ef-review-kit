# EF Review Report: {Solution name}

**Date**: {date} | **Mode**: {full/slow/upgrade} | **Reviewed by**: Claude (ef-review-kit)

## Summary
| Project | EF | Version | Target FW | Support | Health |
|---|---|---|---|---|---|
| {Api} | EF Core | 8.0.10 | net8.0 | Ended Nov 2026 | 62/100 |

Health score = 100 minus confirmed findings weighted: critical 10, high 5, medium 2, low 0.5, info 0 (floor 0).

**Findings**: {n} critical, {n} high, {n} medium, {n} low, {n} info ({n} scanner hits dropped as false positives).

## Top 10 fixes by impact
| # | ID | Severity | Where | Fix | Effort |
|---|---|---|---|---|---|
| 1 | EF001 | high | OrderService.cs:88 `GetOrdersWithCustomers` | Replace per-order lookup with one query | S |

Effort: S (< 1h), M (half day), L (days).

## Findings by category
### Wrong usage and bugs
#### [EF001] N+1 in `OrderService.GetOrdersWithCustomers` (high)
**File**: `src/Api/Services/OrderService.cs:88`
**Why**: {specific explanation with entity names, expected row counts if known}
**Before**
```csharp
...
```
**After**
```csharp
...
```
**Min EF version**: all | **Verify**: {how to measure}

### Slow queries
### Model configuration
### Migrations and schema
### Transactions and integrity
### Security
### Memory and connections
### Architecture, testing, observability
### Modernisation (new features)

## Slow query analysis (if Query Store data provided)
| Rank | Tag / Query | Avg ms | Execs | Reads | Cause | Fix |
|---|---|---|---|---|---|---|

Index changes (as EF config + migration):
```csharp
```

## Upgrade readiness
Current: {x} -> Recommended: {EF Core 10 LTS / 11}
Blockers, breaking changes that affect this codebase (with file:line), plan.

## Free wins from upgrading

## Benchmark plan
Top 3 perf fixes with BenchmarkDotNet setup (see `BenchmarkTemplate.cs`), dataset size, metric (mean ms, allocations, logical reads).

## Needs data
Findings marked `needs-data` and what to measure.

## Next steps
Say: "Reply with IDs to fix (for example `fix EF001 EF004`) or `fix all high`."
