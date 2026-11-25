# EF6 specifics (legacy ASP.NET MVC / WebForms / WCF)

Most anti-patterns in `antipatterns.md` apply. Differences and EF6-only issues:

## Defaults that hurt
- **Lazy loading on by default** with `virtual` navigations: N+1 in Razor views, GridView/Repeater binding, and serialisation. Set `Configuration.LazyLoadingEnabled = false` on read paths, use `.Include("Nav")` or `.Include(x => x.Nav)`.
- **Proxy creation** (`ProxyCreationEnabled`) breaks JSON serialisation (loops, huge payloads). Disable for API contexts, project to DTOs.
- **AutoDetectChanges** on: `Add` in loops gets O(n²). For imports: `AutoDetectChangesEnabled = false` + `AddRange`, SaveChanges per chunk, new context per chunk.
- **Contains** inlines every value as a constant: slow translation, plan cache bloat. Chunk lists (for example 500) or use a TVP via stored proc.
- **First query is slow** (model build + view generation): pre-generate views (EF Power Tools / `EFInteractiveViews`), use NGen'd EntityFramework.dll, warm up in `Application_Start`.

## WebForms / MVC5 lifetime problems
- Context per request: should be created per request (DI container `InstancePerRequest` / `PerWebRequest`) and disposed. Look for static contexts in `Global.asax`, base pages, or static helper classes (EF008, critical).
- Context stored in `Session` or `Application`: critical, same as singleton.
- `Page_Load` doing queries per row in `ItemDataBound` events: N+1 (EF001).
- `ObjectDataSource`/`EntityDataSource` with no paging: full table loads (EF013). Use server-side paging (`EnablePaging`, `SelectCountMethod`).

## Logging and slow queries
- `context.Database.Log = s => Trace.WriteLine(s);`
- Slow query logging: implement `IDbCommandInterceptor` (`ReaderExecuting/Executed` with a Stopwatch), register via `DbInterception.Add` or `DbConfiguration`.
- No `TagWith`: interceptor can prepend `/* Caller */` using a context property or AsyncLocal.

## Raw SQL
`Database.SqlQuery<T>`, `Database.ExecuteSqlCommand`, `DbSet.SqlQuery`: parameterise with `@p0` + `SqlParameter` (EF005).

## Bulk operations
EF6 has no ExecuteUpdate/ExecuteDelete. Options: `ExecuteSqlCommand` with parameters for set-based updates, `SqlBulkCopy` for inserts, or a library (EntityFramework.Extended is dead; Z.EntityFramework.Extensions is commercial).

## Retry
Azure SQL: `SetExecutionStrategy("System.Data.SqlClient", () => new SqlAzureExecutionStrategy())` in a `DbConfiguration`. User-initiated transactions need the strategy suspended.

## Upgrade path
Latest is EF 6.5.x (also runs on modern .NET). If staying on .NET Framework, upgrade to 6.5 and fix the issues above; that alone gives most of the perf wins. For EF Core migration readiness see `upgrade-readiness.md` (EF809).
