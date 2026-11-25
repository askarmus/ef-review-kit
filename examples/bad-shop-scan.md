# EF scan (candidates) for `examples/bad-shop`

Detected: **EF Core 8** | target: 11 | files: 5 | DbContexts: AppDbContext, ShopEntities

**Health (unverified): 0/100** | critical: 8, high: 12, medium: 25, low: 2, info: 11

> Heuristic candidates. Verify each by reading the code; recompute health after dropping false positives.

| Sev | ID | Where | Finding | Conf |
|---|---|---|---|---|
| critical | EF005 | `legacy/Shop.Web/LegacyRepo.cs:8` | `SqlQuery<Product>` gets a SQL string built from values: SQL injection risk. | high |
| critical | EF005 | `src/Shop.Api/Services/OrderService.cs:50` | `FromSqlRaw` gets a SQL string built from values: SQL injection risk. | medium |
| critical | EF005 | `src/Shop.Api/Services/OrderService.cs:51` | `FromSqlRaw` gets a SQL string built from values: SQL injection risk. | high |
| critical | EF008 | `src/Shop.Api/Services/OrderService.cs:7` | Static DbContext field: one context for the whole app. | medium |
| critical | EF018 | `src/Shop.Api/Services/OrderService.cs:91` | Task.WhenAll runs several queries on the same DbContext concurrently. | medium |
| critical | EF201 | `src/Shop.Api/Migrations/20261101_Drop.cs:6` | `DropColumn` in migration Up(): data is lost. | medium |
| critical | EF402 | `src/Shop.Api/Data/AppDbContext.cs:16` | Connection string with a password hard-coded in source. | medium |
| critical | EF402 | `src/Shop.Api/appsettings.json:1` | Connection string with a password in committed config (non-development config). | medium |
| high | EF001 | `src/Shop.Api/Services/OrderService.cs:15` | Database query inside `foreach` loop runs once per item. | medium |
| high | EF002 | `src/Shop.Api/Services/OrderService.cs:24` | Query is materialised, then `Where` runs in memory. | medium |
| high | EF004 | `src/Shop.Api/Services/OrderService.cs:43` | SaveChanges inside `foreach` loop: one round trip and transaction per item. | medium |
| high | EF006 | `src/Shop.Api/Services/OrderService.cs:79` | `CountAsync(...).Result` blocks the thread; deadlock/thread starvation risk. | medium |
| high | EF013 | `src/Shop.Api/Services/OrderService.cs:29` | Loads every row of the table with no filter or paging. | low |
| high | EF013 | `src/Shop.Api/Services/OrderService.cs:91` | Loads every row of the table with no filter or paging. | low |
| high | EF103 | `src/Shop.Api/Data/AppDbContext.cs:20` | Cascade delete: deleting the parent deletes all children. | low |
| high | EF202 | `src/Shop.Api/Migrations/20261101_Drop.cs:8` | `RenameColumn`: older app instances, views, procs and raw SQL using the old name will break. | low |
| high | EF401 | `src/Shop.Api/Data/AppDbContext.cs:15` | EnableSensitiveDataLogging is not guarded by a development check. | medium |
| high | EF502 | `src/Shop.Api/Program.cs:7` | `Worker` is a long-lived hosted service but takes a DbContext in its constructor. | medium |
| high | EF801 | `src/Shop.Api/Shop.Api.csproj` | Shop.Api uses EF Core 8.0.10 (support ended Nov 10 2026). Checked 2026-11-25. | medium |
| high | EF804 | `src/Shop.Api/appsettings.json:1` | Entra ID authentication in connection string: EF Core 11 uses SqlClient 7, which moved Azure auth to a separate package. | medium |
| medium | EF003 | `src/Shop.Api/Services/OrderService.cs:35` | Count() compared with 0 scans all matches. | medium |
| medium | EF007 | `src/Shop.Api/Services/OrderService.cs:34` | Synchronous EF call in async method `HasOrders` blocks a thread. | medium |
| medium | EF009 | `src/Shop.Api/Services/OrderService.cs:58` | 3 Include/ThenInclude in one query: if 2+ are collections, rows multiply (cartesian explosion). | low |
| medium | EF010 | `src/Shop.Api/Services/OrderService.cs:12` | `GetOrdersWithCustomers` only reads, but the query tracks entities. | low |
| medium | EF010 | `src/Shop.Api/Services/OrderService.cs:24` | `GetActive` only reads, but the query tracks entities. | low |
| medium | EF010 | `src/Shop.Api/Services/OrderService.cs:29` | `GetAllOrders` only reads, but the query tracks entities. | low |
| medium | EF010 | `src/Shop.Api/Services/OrderService.cs:50` | `Search` only reads, but the query tracks entities. | low |
| medium | EF010 | `src/Shop.Api/Services/OrderService.cs:58` | `GetDetails` only reads, but the query tracks entities. | low |
| medium | EF011 | `src/Shop.Api/Services/OrderService.cs:69` | RemoveRange over a query result loads rows just to delete them. | medium |
| medium | EF012 | `src/Shop.Api/Services/OrderService.cs:64` | Loads entities then sets properties in a loop and saves: set-based update candidate. | low |
| medium | EF015 | `src/Shop.Api/Services/OrderService.cs:53` | `ToLower` on a column inside the predicate stops index seeks. | medium |
| medium | EF017 | `(solution)` | EF6 with virtual navigations and lazy loading never disabled: N+1 risk in views/serialisation. | medium |
| medium | EF101 | `src/Shop.Api/Data/AppDbContext.cs:3` | `Order.Total` is decimal with no precision: defaults to decimal(18,2), values can be truncated. | medium |
| medium | EF104 | `(solution)` | No concurrency token on any entity: concurrent edits silently overwrite each other. | medium |
| medium | EF205 | `src/Shop.Api/Program.cs:5` | Migrations applied at application startup. | medium |
| medium | EF301 | `src/Shop.Api/Services/OrderService.cs:86` | `Twice` calls SaveChanges 2 times with no transaction: partial commits possible. | medium |
| medium | EF303 | `(solution)` | No retry strategy for transient SQL errors and the app targets Azure SQL. | medium |
| medium | EF403 | `src/Shop.Api/Services/OrderService.cs:98` | Global query filters are bypassed here. | low |
| medium | EF505 | `legacy/Shop.Web/LegacyRepo.cs:7` | `new ShopEntities(...)` without using/Dispose: leaked connections and change trackers. | low |
| medium | EF603 | `tests/Shop.Tests/OrderTests.cs:1` | Tests use the InMemory provider: no SQL translation, constraints or transactions. | medium |
| medium | EF803 | `src/Shop.Api/Data/AppDbContext.cs:16` | EF Core 11 defaults SQL Server compatibility level to 160 (2022). | medium |
| medium | EF803 | `src/Shop.Api/Program.cs:2` | EF Core 11 defaults SQL Server compatibility level to 160 (2022). | medium |
| medium | EF805 | `src/Shop.Api/Shop.Api.csproj:2` | EFOptimizeContext property is removed in EF Core 11. | medium |
| medium | EF807 | `src/Shop.Api/Program.cs:5` | After upgrading to EF Core 9+, Migrate() throws PendingModelChangesWarning when the model and migrations differ. | medium |
| medium | EF810 | `src/Shop.Api/Shop.Api.csproj` | mixed EF Core major versions in one project: [8, 9] | medium |
| low | EF014 | `src/Shop.Api/Services/OrderService.cs:12` | In-memory list Contains() becomes a SQL IN / OPENJSON / parameter list; slow and plan-cache heavy if the list is large. | low |
| low | EF102 | `src/Shop.Api/Data/AppDbContext.cs:3` | `Order` has 2 string properties without max length: Status, Email. They become nvarchar(max). | low |
| info | EF105 | `src/Shop.Api/Data/AppDbContext.cs:21` | Owned type mapping; complex types are the newer value-object mapping. | medium |
| info | EF503 | `(solution)` | AddDbContext without pooling. | medium |
| info | EF602 | `src/Shop.Api/Services/OrderService.cs:96` | `QueryAll` returns IQueryable: query runs later, outside the data layer. | low |
| info | EF604 | `(solution)` | No TagWith/TagWithCallSite: production SQL cannot be traced back to code. | medium |
| info | EF605 | `(solution)` | No SQL logging, command interceptor or OpenTelemetry found. | medium |
| info | EF702 | `src/Shop.Api/Services/OrderService.cs:72` | OrderBy(...).First() to get the min/max element. Needs EF Core 11+ (current 8): suggest after upgrade. | medium |
| info | EF702 | `src/Shop.Api/Services/OrderService.cs:76` | OrderBy(...).First() to get the min/max element. Needs EF Core 11+ (current 8): suggest after upgrade. | medium |
| info | EF705 | `src/Shop.Api/Data/AppDbContext.cs:22` | Several conditions combined in one query filter; IgnoreQueryFilters removes all of them. Needs EF Core 10+ (current 8): suggest after upgrade. | medium |
| info | EF802 | `legacy/Shop.Web/Shop.Web.csproj` | Shop.Web targets .NET Framework (net48); EF Core 11 needs .NET 11. | medium |
| info | EF808 | `(solution)` | Collection Contains translation changes in EF Core 10 (multiple parameters instead of OPENJSON). | medium |
| info | EF809 | `legacy/Shop.Web/Shop.Web.csproj` | Shop.Web is EF6 6.4.4: see EF6 to EF Core readiness table. | medium |

## Fix hints

- **EF001 Query inside a loop (N+1)**: Load everything needed in one query before the loop (Where + Contains, Include, or projection), then look up in memory. (references/antipatterns.md)
- **EF002 Materialised before filtering (client-side evaluation)**: Move the filter/paging/aggregate before ToList so it runs in SQL. AsEnumerable is fine only at the very end for untranslatable C#. (references/antipatterns.md)
- **EF003 Count() > 0 instead of Any()**: Use Any()/AnyAsync() (EXISTS). (references/antipatterns.md)
- **EF004 SaveChanges inside a loop**: Call SaveChanges once after the loop (chunk very large batches). (references/antipatterns.md)
- **EF005 Raw SQL built with concatenation/interpolation (SQL injection)**: Use FromSql/ExecuteSql with an interpolated string (parameterised), or pass parameters ({0} / SqlParameter). Whitelist dynamic identifiers. (references/security.md)
- **EF006 Blocking on async EF call (.Result/.Wait/GetResult)**: Make the call chain async and await it (or use the sync EF API consistently in legacy sync code). (references/antipatterns.md)
- **EF007 Sync EF call inside async method**: Use the Async version (ToListAsync, FirstOrDefaultAsync, SaveChangesAsync) and pass a CancellationToken. (references/antipatterns.md)
- **EF008 DbContext with singleton/static lifetime**: Create a context per request/unit of work (DI scoped, or using new ... per operation). (references/antipatterns.md)
- **EF009 Multiple Includes without AsSplitQuery (cartesian explosion risk)**: Add .AsSplitQuery() (or project with Select). Needs a stable OrderBy when paging. (references/antipatterns.md)
- **EF010 Read-only query without AsNoTracking**: Add .AsNoTracking() or project to a DTO with Select. Skip if the entities are modified later by the caller. (references/antipatterns.md)
- **EF011 Load-then-delete; use ExecuteDelete**: Use query.ExecuteDelete(Async)(). (references/antipatterns.md)
- **EF012 Load-modify-save loop; use ExecuteUpdate**: Use ExecuteUpdate(Async)(s => s.SetProperty(...)) if no audit/concurrency logic depends on tracking. (references/antipatterns.md)
- **EF013 Unbounded full-table load**: Filter and page in SQL (Where + OrderBy + Skip/Take or keyset). For exports, stream with AsAsyncEnumerable + AsNoTracking. OK for small lookup tables. (references/antipatterns.md)
- **EF014 Contains() over an in-memory list (large IN / OPENJSON)**: Cap or chunk the list; for very large sets use a temp table/TVP. Behaviour differs by EF version (see reference). (references/antipatterns.md)
- **EF015 Non-sargable predicate (function on column)**: Rely on case-insensitive collation, normalise data on write, or use a range (x.Date >= d && x.Date < d.AddDays(1)). (references/antipatterns.md)
- **EF017 Lazy loading enabled (hidden N+1)**: Set Configuration.LazyLoadingEnabled = false on read/API contexts and use Include. (references/antipatterns.md)
- **EF018 Parallel operations on one DbContext**: Await sequentially, or create one context per branch with IDbContextFactory. (references/antipatterns.md)
- **EF101 decimal property without precision**: Add [Precision(18,4)] / .HasPrecision(p,s), or a ConfigureConventions default. (references/model-config.md)
- **EF102 string properties without max length (nvarchar(max))**: Add [MaxLength]/HasMaxLength or a ConfigureConventions default; IsUnicode(false) for ASCII codes. (references/model-config.md)
- **EF103 Cascade delete configured: review blast radius**: Confirm intent; for business data prefer Restrict/NoAction + soft delete. (references/model-config.md)
- **EF104 No concurrency tokens anywhere**: Add a RowVersion to contested entities (orders, stock, balances) and handle DbUpdateConcurrencyException. (references/model-config.md)
- **EF105 Owned types: consider complex types**: Consider ComplexProperty (EF8+, JSON in EF10+, keys/indexes and TPT/TPC in EF11). (references/model-config.md)
- **EF201 Destructive migration operation**: Make sure data is migrated/backed up first; if this is a rename EF generated as drop+add, use RenameColumn. (references/migrations.md)
- **EF202 Rename in migration (rolling deploy / raw SQL break risk)**: Use expand/contract for zero-downtime deploys; search raw SQL for the old name. (references/migrations.md)
- **EF205 Database.Migrate() at app startup**: Apply migrations from the pipeline (idempotent script or bundle). On EF Core 9+ this throws if the model has pending changes. (references/migrations.md)
- **EF301 Multiple SaveChanges without a transaction**: Use a single SaveChanges, or wrap in BeginTransaction (inside CreateExecutionStrategy().Execute if retries are on). (references/data-integrity.md)
- **EF303 No retry strategy for transient SQL errors**: EF Core: EnableRetryOnFailure() or UseAzureSql(); EF6: SqlAzureExecutionStrategy. (references/data-integrity.md)
- **EF401 EnableSensitiveDataLogging not limited to development**: Wrap in if (env.IsDevelopment()) ... or drive it from configuration that is off in production. (references/security.md)
- **EF402 Connection string with password in code/config**: Move to user-secrets / Key Vault / environment variables or use Managed Identity; rotate the password. (references/security.md)
- **EF403 IgnoreQueryFilters: check tenant/soft-delete leak**: Confirm admin-only use and that tenant filtering is still applied; with EF Core 10 ignore only the named filter you need. (references/security.md)
- **EF502 DbContext injected into a long-lived hosted service**: Inject IDbContextFactory<T> or IServiceScopeFactory and create a context per unit of work. (references/memory-connections.md)
- **EF503 Consider DbContext pooling**: For high-throughput APIs consider AddDbContextPool (if the context has no per-request state). (references/memory-connections.md)
- **EF505 DbContext created with new and maybe not disposed**: Wrap in using / await using, or get it from DI / IDbContextFactory. (references/memory-connections.md)
- **EF602 IQueryable returned from public method**: Return materialised DTOs, or keep IQueryable internal to the data layer. (references/architecture-testing-observability.md)
- **EF603 InMemory provider used for tests**: Use SQLite in-memory for unit-ish tests and Testcontainers SQL Server for integration tests. (references/architecture-testing-observability.md)
- **EF604 No query tags (TagWith) anywhere**: Tag hot queries: .TagWith("Service.Method") or .TagWithCallSite(). (references/architecture-testing-observability.md)
- **EF605 No SQL logging / slow query interceptor found**: Add a slow query interceptor (see slow-query-playbook.md) and OTel DB instrumentation. (references/architecture-testing-observability.md)
- **EF702 OrderBy(...).First(); consider MaxBy/MinBy**: Use MaxBy/MinBy (MaxByAsync) on EF Core 11+. (references/features-by-version.md)
- **EF705 Combined query filter; consider named filters**: Use named filters (EF Core 10+) so you can ignore only one, e.g. soft delete but not tenant. (references/features-by-version.md)
- **EF801 EF version out of support**: Plan an upgrade to EF Core 10 (LTS) or 11. (references/upgrade-readiness.md)
- **EF802 Target framework blocks EF Core upgrade**: Upgrade the runtime first, or stay on EF6 6.5 for this project. (references/upgrade-readiness.md)
- **EF803 UseSqlServer without explicit compatibility level (EF 11 default changes to 160)**: If prod runs an older SQL Server/compat level, add o => o.UseCompatibilityLevel(150) (or your level). (references/upgrade-readiness.md)
- **EF804 Entra ID / Azure AD auth: needs separate package on EF 11 (SqlClient 7)**: Add the Azure authentication package named in the EF Core 11 breaking-changes doc. (references/upgrade-readiness.md)
- **EF805 EFOptimizeContext MSBuild property removed in EF 11**: Delete it and use the current compiled model approach. (references/upgrade-readiness.md)
- **EF807 Migrate() throws on pending model changes from EF 9**: Run `dotnet ef migrations has-pending-model-changes` in CI before upgrading. (references/upgrade-readiness.md)
- **EF808 Contains translation changes in EF 10 (multiple parameters)**: Compare SQL/plans for queries with large Contains lists after upgrading. (references/upgrade-readiness.md)
- **EF809 EF6 to EF Core migration readiness item**: Fill in the readiness table in the report (EDMX, ObjectContext, lazy loading, client eval, stored procs). (references/upgrade-readiness.md)
- **EF810 Mixed EF package versions**: Align all EF packages to one version (Central Package Management). (references/upgrade-readiness.md)
