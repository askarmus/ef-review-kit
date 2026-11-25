# Wrong usage and bugs (EF001 to EF018)

Each rule: ID, severity, min version, what to look for, why, fix. "All" = EF6 and EF Core unless noted.

---

## EF001 Query inside a loop (N+1) | high | All
**Look for**: `foreach`/`for`/`while` body that calls the context (`.ToList`, `.First*`, `.Single*`, `.Find`, `.Any`, `.Count`, `await _db...`), or touches a lazy-loaded navigation per item.
**Why**: 1 query becomes N+1 round trips. Fine on dev with 5 rows, dies in prod.
```csharp
// Bad
foreach (var order in orders)
    order.Customer = await _db.Customers.FindAsync(order.CustomerId);

// Good: one query
var ids = orders.Select(o => o.CustomerId).Distinct().ToList();
var customers = await _db.Customers.Where(c => ids.Contains(c.Id)).ToDictionaryAsync(c => c.Id);
foreach (var order in orders) order.Customer = customers[order.CustomerId];
// Or: Include / projection in the original query
```

## EF002 Materialize before filter (client-side evaluation) | high | All
**Look for**: `.ToList()`, `.ToArray()`, `.AsEnumerable()` followed by `.Where/.OrderBy/.Select/.Count/.Any/.First/.Skip/.Take/.Sum`.
**Why**: loads the whole table into memory and filters in C#.
```csharp
// Bad
var active = _db.Users.ToList().Where(u => u.IsActive).Take(20);
// Good
var active = await _db.Users.Where(u => u.IsActive).Take(20).ToListAsync();
```
**Note**: `AsEnumerable()` is legit at the very end to call a C# method that cannot translate, after filtering/paging in SQL.

## EF003 Count() > 0 instead of Any() | medium | All
`Any()` becomes `EXISTS` and stops at the first row. `Count()` scans all matches.

## EF004 SaveChanges inside a loop | high | All
**Why**: one round trip + one transaction per item. Also partial-commit risk if item 37 fails.
**Fix**: add/update all, call `SaveChanges` once after the loop (EF Core batches). For pure updates/deletes, see EF011/EF012. For very large imports, chunk (for example 1,000 per SaveChanges) and use a new context per chunk, or SqlBulkCopy / EFCore.BulkExtensions.

## EF005 Raw SQL built with string concat or interpolation | critical | All
See `security.md`. `FromSqlRaw($"... {x}")`, `ExecuteSqlRaw("..." + x)`, EF6 `Database.SqlQuery<T>("..." + x)`.
**Fix**: `FromSql($"... {x}")` / `FromSqlInterpolated` / `ExecuteSql` (parameterised), or `FromSqlRaw("... {0}", x)` / `SqlParameter`.

## EF006 Blocking on async | high | All
`.Result`, `.Wait()`, `.GetAwaiter().GetResult()` on EF async calls. Thread pool starvation under load, deadlocks on ASP.NET (non-Core) and WebForms sync contexts.
**Fix**: async all the way up. In legacy WebForms use `RegisterAsyncTask` / `Page.Async="true"`, or stay fully sync.

## EF007 Sync EF call inside async method | medium | EF6 6.0+, EF Core
`async Task<...>` method using `.ToList()`, `.First()`, `.SaveChanges()`. Blocks a thread during I/O.
**Fix**: `ToListAsync`, `FirstAsync`, `SaveChangesAsync`, pass `CancellationToken`.

## EF008 DbContext lifetime wrong | critical | All
`AddSingleton<MyDbContext>`, `static MyDbContext`, context stored in a singleton service field, or `ServiceLifetime.Singleton` in `AddDbContext`.
**Why**: DbContext is not thread safe. Concurrent requests corrupt the change tracker, throw "A second operation was started on this context", leak memory forever.
**Fix**: scoped (default `AddDbContext`). In singletons/hosted services inject `IDbContextFactory<T>` or `IServiceScopeFactory` and create a short-lived context per unit of work.

## EF009 Multiple collection Includes (cartesian explosion) | medium | EF Core 5+
Two or more collection `Include`/`ThenInclude` on one query. Rows = A x B x C.
**Fix**: `.AsSplitQuery()` per query, or globally `UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery)` then `.AsSingleQuery()` where needed. Better: project only the needed columns with `Select`.
**Trade-off**: split queries are not one consistent snapshot unless in a transaction, and with `Skip/Take` need a stable unique `OrderBy`.
**EF 11 free win**: split queries drop needless to-one joins and redundant ORDER BY columns (Microsoft reports up to 29% faster).

## EF010 Read-only query tracked | medium | All
Query in a Get/List/Search path, results never modified/saved, no `AsNoTracking()`.
**Fix**: `.AsNoTracking()` (or `.AsNoTrackingWithIdentityResolution()` when the graph has repeated entities). For read-heavy contexts set `UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking)` and opt in with `.AsTracking()`.
Projections into DTOs (`Select(x => new Dto{...})`) are not tracked anyway; best option for APIs.
**Do not** add AsNoTracking if the entity is later modified and saved in the same flow.

## EF011 Load-then-delete | medium | EF Core 7+
`foreach (...) _db.Remove(x)` or `RemoveRange(await query.ToListAsync())`.
**Fix (EF7+)**: `await _db.Logs.Where(l => l.Created < cutoff).ExecuteDeleteAsync();`
**Caveat**: bypasses change tracker, interceptors, SaveChanges overrides (audit, soft delete). Check for those before suggesting.

## EF012 Load-modify-save for set-based updates | medium | EF Core 7+
Loop that sets the same property on many loaded entities, then SaveChanges.
**Fix (EF7+)**: `ExecuteUpdateAsync(s => s.SetProperty(o => o.Status, OrderStatus.Archived))`.
**EF10+**: ExecuteUpdate accepts a normal lambda, so conditional setters are easy:
```csharp
await _db.Blogs.ExecuteUpdateAsync(s =>
{
    s.SetProperty(b => b.Views, 8);
    if (nameChanged) s.SetProperty(b => b.Name, "foo");
});
```
Same caveats as EF011 (audit fields, RowVersion, interceptors).

## EF013 Unbounded full-table load | high | All
`_db.Orders.ToListAsync()` with no `Where`/`Take`, in an API or UI path.
**Fix**: filter + page (`Skip/Take` with stable `OrderBy`, or keyset paging `Where(x => x.Id > lastId).Take(n)` for deep pages). For exports, stream: `AsAsyncEnumerable()` + `AsNoTracking()`.

## EF014 Large Contains list | medium | All (behaviour varies by version)
`ids.Contains(x.Id)` with a list that can be hundreds/thousands.
- EF6: inlines constants, huge SQL, plan cache pollution, slow translation.
- EF Core 8/9: uses `OPENJSON` (needs SQL Server compat level 130+); cardinality estimates can be bad.
- EF Core 10: default is multiple scalar parameters (padded); tunable with `UseParameterizedCollectionMode`.
- EF Core 11 + SQL Server 2025 (compat 170): primitive collection Contains can use `JSON_CONTAINS`.
**Fix**: cap list size, batch in chunks, or join to a temp/TVP table for very large sets.

## EF015 Non-sargable predicate | medium | All
`Where(x => x.Email.ToLower() == email)`, `x.Name.Trim()`, `x.Created.Date == d`, `x.Created.Year == 2025`, `string.Format`/concat on the column side.
**Why**: function on the column = index can't seek.
**Fix**: use a case-insensitive collation (SQL Server default CI), normalise data on write, or use ranges: `x.Created >= d && x.Created < d.AddDays(1)`.
**EF 11 free win**: redundant `CAST` of a column to its own type is stripped so indexes can be used.

## EF016 Include ignored by projection | low | EF Core
`.Include(x => x.Items).Select(x => new Dto{...})`: Include does nothing when you project. Remove it or include the needed fields in the projection.

## EF017 Lazy loading enabled | medium | All
EF Core `UseLazyLoadingProxies()`; EF6 `virtual` navigations with `LazyLoadingEnabled` default true.
**Why**: hidden N+1, especially in views, serializers (JSON serializing a proxy walks the graph), and loops.
**Fix**: eager load / project; in EF6 set `Configuration.LazyLoadingEnabled = false` for API/read paths; never serialize entities directly.

## EF018 Parallel queries on one context | critical | All
`Task.WhenAll(_db.A.ToListAsync(), _db.B.ToListAsync())` or `Parallel.ForEach` using the same context.
**Fix**: await sequentially, or use `IDbContextFactory` and a separate context per parallel branch.
