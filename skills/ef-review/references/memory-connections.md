# Memory and connections (EF501 to EF505)

## EF501 Large result sets materialised | high | All
`ToList()` on exports/reports with 100k+ rows. Memory spikes, LOH allocations, GC pauses.
**Fix**: stream:
```csharp
await foreach (var row in _db.Orders.AsNoTracking().Where(...).AsAsyncEnumerable().WithCancellation(ct))
    await writer.WriteAsync(row);
```
EF6: iterate the `IQueryable` directly (`foreach` streams) with `AsNoTracking()`.

## EF502 Long-lived context in background work | high | All
DbContext injected into a `BackgroundService`/`IHostedService` (singletons), Hangfire/Quartz jobs keeping one context across thousands of items, or WinForms/WPF with one context for the app lifetime. Change tracker grows forever, stale data, memory leak.
**Fix**: `IDbContextFactory<T>` / `IServiceScopeFactory`, new context per job/batch. For big batches, `ChangeTracker.Clear()` (EF Core 5+) between chunks.

## EF503 Context pooling | info | EF Core 2.0+ (`AddDbContextPool`), 6+ (`AddPooledDbContextFactory`)
High-throughput APIs: `AddDbContextPool<T>()` cuts context setup cost. Not compatible with contexts that hold per-request state in fields (tenant id set in constructor): use the pooled factory + `IDbContextFactory` pattern for those.

## EF504 ToAsyncEnumerable on EF queries | low | EF Core 11 analyzer
`ToAsyncEnumerable()` (System.Linq.Async / .NET 10 BCL) on an EF query goes through the sync path. Use `AsAsyncEnumerable()`. EF Core 11 ships an analyzer + code fix.

## EF505 Connection pool exhaustion
Symptoms: "Timeout expired... max pool size was reached". Causes: blocking async (EF006), contexts not disposed (manual `new MyContext()` without `using`), long transactions, `MultipleActiveResultSets` hiding problems, opening `Database.GetDbConnection()` manually and not closing.
**Check**: every manual `new XContext(...)` is in a `using`. Every `GetDbConnection().Open()` has a matching close.

## Tracking cost
- Tracking 10k+ entities makes DetectChanges slow. For bulk inserts in EF6 set `Configuration.AutoDetectChangesEnabled = false` and use `AddRange`.
- EF Core: `ChangeTracker.AutoDetectChangesEnabled = false` for big batch inserts, then call `DetectChanges()` once if needed.
