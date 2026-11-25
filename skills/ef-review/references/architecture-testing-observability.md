# Architecture, testing, observability (EF601 to EF607)

## EF601 Generic repository over DbContext | info
`IRepository<T>` with `GetAll()`, `GetById()`, `Find(Expression)` wrapping DbSet. Common problems:
- `GetAll()` returns `IEnumerable<T>` or `List<T>`, so callers filter in memory (EF002/EF013).
- No way to Include, project, AsNoTracking, or page efficiently.
- SaveChanges inside each repository method = no unit of work (EF301).
**Advice**: DbContext already is a unit of work + repository. Prefer query services / specific repositories with intention-revealing methods returning DTOs. Don't recommend a big rewrite: suggest adding projection-friendly methods for hot paths.

## EF602 IQueryable leaking out | info
Public service/repository methods returning `IQueryable<T>` to controllers/views: queries execute late (in the view, after context disposal), N+1 from Razor loops, hard to see what SQL runs. Return materialised DTOs from the data layer.

## EF603 InMemory provider in tests | medium
`UseInMemoryDatabase` does not enforce relational behaviour: no transactions, no constraints, no SQL translation, different case sensitivity. Tests pass, prod fails.
**Fix**: SQLite in-memory for fast tests (still not SQL Server), or Testcontainers SQL Server for integration tests. Microsoft docs recommend against InMemory for testing.

## EF604 No query tags | info
No `TagWith` / `TagWithCallSite` anywhere: production SQL can't be mapped back to code. Suggest tagging hot paths.

## EF605 No slow query visibility | info
No `LogTo`, no logging config for `Microsoft.EntityFrameworkCore.Database.Command`, no interceptor, no OpenTelemetry. Suggest the SlowQueryInterceptor in `slow-query-playbook.md` and OTel instrumentation.

## EF606 Read/write split | info
Read-heavy dashboards/reports on the same tracked model as writes. Suggest: no-tracking read context (`UseQueryTrackingBehavior(NoTracking)`), projections, keyless entities on views (`HasNoKey().ToView(...)`), read replica connection, or Dapper for complex reports. Mention CQRS only as a direction, not a rewrite.

## EF607 Business logic in mapping / entity config
Validation, defaults with side effects, or computed business rules inside `OnModelCreating`/`IEntityTypeConfiguration`. Move to domain/services.

## Testing gaps to report
- No integration tests that hit a real database for the main queries.
- No test that applies all migrations from scratch.
- No CI check for pending model changes (`dotnet ef migrations has-pending-model-changes`, EF Core 8+).

## Observability checklist
- OpenTelemetry traces with DB spans.
- Slow query interceptor with threshold.
- Query Store on in prod.
- EF Core metrics (EF Core 9+ emits `System.Diagnostics.Metrics`: queries, SaveChanges, cache hit rate) via `dotnet-counters` or OTel.
