# New features by version (EF701 to EF708 + catalogue)

Only recommend what the detected version supports. Otherwise label: "available after upgrade to EF Core X".

## Scanner modernisation rules
| ID | Pattern found | Suggest | Min version |
|---|---|---|---|
| EF701 | `GroupJoin(...).SelectMany(... DefaultIfEmpty())` or query syntax `join ... into g from x in g.DefaultIfEmpty()` | `LeftJoin(...)` / `RightJoin(...)` | EF Core 10 |
| EF702 | `OrderBy(x => k).First()` / `OrderByDescending(...).FirstOrDefault()` to get min/max item | `MinBy(x => k)` / `MaxBy(x => k)` (+ `MaxByAsync`) | EF Core 11 |
| EF703 | `FromSqlRaw` on a fake entity/keyless type just to read a DTO | `Database.SqlQuery<T>(...)` for unmapped types | EF Core 8 |
| EF704 | Hot simple query called very often | `EF.CompileAsyncQuery` | EF Core 2+ |
| EF705 | Several `HasQueryFilter` calls / filters combined with `&&`, and code that uses `IgnoreQueryFilters()` | Named filters, ignore one by name | EF Core 10 |
| EF706 | Full outer join emulated with left join + right join + Union/Concat | `FullJoin(...)` | EF Core 11 |
| EF707 | ExecuteUpdate with hand-built expression trees for conditional setters | Normal lambda with `if` | EF Core 10 |
| EF708 | `OwnsOne/OwnsMany` for value objects | Complex types (`ComplexProperty`) | EF Core 8 (cols), 10 (JSON), 11 (TPT/TPC, keys/indexes) |

## Catalogue

### EF Core 5
`AsSplitQuery`, filtered Include (`Include(b => b.Posts.Where(...))`), `ToQueryString()`, `LogTo`, `ChangeTracker.Clear()`, many-to-many without join entity, index `IncludeProperties`.

### EF Core 6
Compiled models (`dotnet ef dbcontext optimize`) for faster startup on big models, `ConfigureConventions` (pre-convention config), temporal tables, migration bundles, `TagWithCallSite`, `AddPooledDbContextFactory`, big query perf gains.

### EF Core 7
`ExecuteUpdate` / `ExecuteDelete`, JSON columns (owned `ToJson`), faster SaveChanges (fewer round trips), TPC inheritance, interceptors for materialisation/query expression, `FromSql` (safe interpolated).

### EF Core 8 (LTS, support ended Nov 10 2026)
Complex types, primitive collections (`List<int>` columns, Contains via OPENJSON), `SqlQuery<T>` for unmapped types, lazy loading for no-tracking queries, HierarchyId, `DateOnly/TimeOnly` on SQL Server, `migrations has-pending-model-changes`.

### EF Core 9 (support ended Nov 10 2026)
`UseSeeding/UseAsyncSeeding`, auto-compiled models, migration locking, `PendingModelChangesWarning` on Migrate, ExecuteUpdate on complex types, `UseAzureSql`, EF metrics, better Cosmos.

### EF Core 10 (LTS, Nov 2025, supported to Nov 2028, needs .NET 10)
- `LeftJoin` / `RightJoin` LINQ operators
- Named query filters (multiple per entity, disable selectively)
- `ExecuteUpdateAsync` takes a normal lambda; ExecuteUpdate on JSON columns
- Complex types mapped to JSON (`ComplexProperty(...).ToJson()`), optional complex types
- SQL Server 2025 / Azure SQL `json` type by default with `UseAzureSql` or compat level 170+
- Vector support: `SqlVector<T>`, `EF.Functions.VectorDistance()`
- Parameterized collections: default multiple scalar parameters (`UseParameterizedCollectionMode` to tune)

### EF Core 11 (Nov 2026, needs .NET 11)
LINQ / SQL:
- Leaner SQL for to-one joins in split queries, redundant ORDER BY keys removed (Microsoft reports up to 29% faster split queries)
- No-op CASTs stripped so indexes can be used
- `GroupBy` improvements (navigations, top-N per group, reference aggregates)
- `FullJoin`, `MaxBy`/`MinBy`, `EF.Functions.JsonPathExists()` (SQL Server 2022+)
Complex types: TPT/TPC support, lambda chaining for nested config, keys and indexes on nested/JSON paths, many fixes (now a real replacement for owned types).
SQL Server:
- `VectorSearch()` + vector indexes in migrations (experimental in SQL Server 2025); vector columns not loaded unless selected (reported ~9x faster local, ~22x on Azure SQL)
- Full-text: `HasFullTextCatalog/HasFullTextIndex` in migrations, `FreeTextTable/ContainsTable` with rank; hybrid search with `FullJoin` + RRF
- `JSON_CONTAINS` for primitive Contains on compat 170, `EF.Functions.JsonContains()`, JSON indexes
- Temporal period columns as normal properties; more DateTimeOffset translations, `EF.Functions.DateTrunc()`
Migrations / tooling: `database update --add`, snapshot records latest migration ID, `.config/dotnet-ef.json`, `--context "*"`, `-NoBuild`, CLI logs to stderr, `ExcludeForeignKeyFromMigrations()`.
Analyzer: warns on `ToAsyncEnumerable` vs `AsAsyncEnumerable`.

## "Free wins from upgrading" (for the report)
Without code changes, upgrading usually brings: leaner SQL (EF 11 join pruning, CAST stripping), faster SaveChanges batching (7+), better Contains translation (8/10/11), lower startup with compiled/auto-compiled models (6/9). Always pair with: run the test suite, compare logged SQL for the top 20 queries before and after (EF 11 can change SQL for LINQ you never touched).
