# Slow query playbook

## 1. Make SQL visible
EF Core:
```csharp
options.UseSqlServer(cs)
       .LogTo(Console.WriteLine, new[] { DbLoggerCategory.Database.Command.Name }, LogLevel.Information);
// Single query:
var sql = query.ToQueryString();
```
EF6:
```csharp
context.Database.Log = s => Debug.WriteLine(s);
```
Never enable `EnableSensitiveDataLogging` in production (EF401).

## 2. Tag queries so SQL maps back to code
```csharp
_db.Orders.TagWith("OrderService.GetOpenOrders").Where(...)
// EF Core 6+: TagWithCallSite() adds file + line automatically
```
Tags appear as `-- comment` at the top of the SQL, visible in Query Store and Profiler. (EF Core 2.2+. EF6 has no TagWith; use an `IDbCommandInterceptor` to prepend a comment.)

## 3. Log slow queries automatically (EF Core 3+)
```csharp
public sealed class SlowQueryInterceptor(ILogger<SlowQueryInterceptor> log) : DbCommandInterceptor
{
    const int ThresholdMs = 500;
    public override ValueTask<DbDataReader> ReaderExecutedAsync(DbCommand cmd, CommandExecutedEventData e,
        DbDataReader result, CancellationToken ct = default)
    {
        if (e.Duration.TotalMilliseconds > ThresholdMs)
            log.LogWarning("Slow query {Ms}ms: {Sql}", e.Duration.TotalMilliseconds, cmd.CommandText);
        return ValueTask.FromResult(result);
    }
}
// options.AddInterceptors(sp.GetRequiredService<SlowQueryInterceptor>())
```
Also: OpenTelemetry (`OpenTelemetry.Instrumentation.EntityFrameworkCore` or SqlClient instrumentation) to see DB spans per request.

## 4. Find the worst queries in SQL Server
Run `scripts/query_store.sql` (read-only). It returns:
- Top queries by avg duration, total CPU, logical reads, executions
- Queries with multiple plans (plan regression / parameter sniffing)
- Missing index suggestions (DMVs)
- Queries containing EF tags

Query Store must be on: `ALTER DATABASE CURRENT SET QUERY_STORE = ON;` (needs DBA, ask the user, do not run it yourself).

## 5. Diagnose causes (check the plan)
| Symptom in plan / SQL | Usual LINQ cause | Fix |
|---|---|---|
| Clustered index scan on big table | no filter, non-sargable filter (EF015), missing index | filter early, sargable predicate, add index |
| Key lookup per row | index lacks selected columns | `IncludeProperties` on index, or project fewer columns |
| Implicit conversion warning | `string` mapped as `nvarchar` vs `varchar` column, or wrong param type | `.IsUnicode(false)` / `HasColumnType("varchar(50)")` to match DB |
| Huge row counts with duplicates | multiple collection Includes (EF009) | AsSplitQuery / projection |
| Many near-identical plans | constants inlined (EF6 Contains, string-built SQL) | parameterise |
| Fast sometimes, slow other times | parameter sniffing | check data skew; `OPTION (RECOMPILE)` via interceptor for that tag only, or fix the index |
| Sort / spill warnings | OrderBy on non-indexed column with paging | index matching ORDER BY, keyset paging |
| OFFSET with big Skip | deep pagination | keyset paging |
| OPENJSON with bad estimates (EF8/9) | large Contains | see EF014 |

## 6. Index suggestions: write them as EF model config
```csharp
modelBuilder.Entity<Order>()
    .HasIndex(o => new { o.CustomerId, o.Status })
    .IncludeProperties(o => new { o.Total, o.CreatedAt })   // SQL Server, EF Core 5+
    .HasFilter("[IsDeleted] = 0")                          // filtered index for soft delete
    .HasDatabaseName("IX_Order_Customer_Status");
```
Rules:
- FKs used in Where/Join should be indexed (EF Core adds FK indexes by convention, EF6 also does for code-first; check DB-first and hand-made schemas).
- Equality columns first, range column last.
- Don't add DMV missing-index suggestions blindly: merge overlapping ones, check write cost on hot tables.
- Index changes go through a new migration (or a DBA script for DB-first / EF6 EDMX).

## 7. Query shape fixes, in order of payoff
1. Project only needed columns (`Select` into DTO).
2. Filter and page in SQL.
3. Kill N+1 (EF001, EF017).
4. AsNoTracking for reads (EF010).
5. Split query for multi-collection loads (EF009).
6. Set-based writes: ExecuteUpdate/ExecuteDelete (EF Core 7+).
7. Compiled queries for very hot, simple queries (`EF.CompileAsyncQuery`), DbContext pooling (`AddDbContextPool` / `AddPooledDbContextFactory`).
8. Raw SQL / Dapper / view / stored procedure for heavy reports.

## 8. Prove it
Before/after with BenchmarkDotNet (`scripts/BenchmarkTemplate.cs`) against a realistic data size, plus logical reads from `SET STATISTICS IO ON`.
