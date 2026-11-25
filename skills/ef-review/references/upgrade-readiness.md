# Upgrade readiness (EF801 to EF810)

Always check the official breaking-changes page for every version you jump over:
https://learn.microsoft.com/ef/core/what-is-new/ (each version has "Breaking changes").
This file lists the ones that bite most often. Treat it as a checklist, not the full list.

## Support status (as of Nov 2026)
| Version | Runtime | Support ends |
|---|---|---|
| EF Core 11 | .NET 11 (STS) | ~Nov 2028 (STS is 24 months; confirm on Microsoft's support page) |
| EF Core 10 | .NET 10 (LTS) | Nov 10 2028 |
| EF Core 9 | .NET 8+ | **Ended Nov 10 2026** |
| EF Core 8 | .NET 8 | **Ended Nov 10 2026** |
| EF Core 7 and older | | Ended |
| EF6 (6.4/6.5) | .NET Framework 4.6.2+ and .NET Core 3.1+ | Maintenance only, no new features |

## EF801 Out of support | high
Project on EF Core 9 or older. Recommend EF Core 10 (LTS) for most enterprise apps; EF Core 11 only if they already move with each .NET release.

## EF802 Runtime blocks the upgrade | info
EF Core 10 needs .NET 10, EF Core 11 needs .NET 11; neither runs on .NET Framework. A `net48` project can only use EF6 (or EF Core 3.1, out of support). Upgrade path = .NET upgrade first.

## Jumping to EF Core 8
- `Contains` on collections uses `OPENJSON`: needs SQL Server compat level 130+; on old DBs set `UseCompatibilityLevel(120)` or queries fail. Watch plan quality on big lists.
- SQL Server `DateOnly/TimeOnly` mapping changes.

## Jumping to EF Core 9
- **EF807** `Migrate()` throws if the model has pending changes (`PendingModelChangesWarning`). Run `dotnet ef migrations has-pending-model-changes` first, add the missing migration. Also throws if Migrate is called in a user transaction.
- Migration lock behaviour changes; custom migration SQL that assumed no lock may need review.

## Jumping to EF Core 10
- Needs .NET 10.
- **EF808** Parameterized collections translate to multiple scalar parameters by default instead of OPENJSON. Usually better plans; compare SQL for queries with big Contains lists.
- JSON columns default to the native `json` type with `UseAzureSql` or compat level 170+: existing nvarchar JSON columns will show up in the next migration as a type change. Decide deliberately.
- ExecuteUpdate API signature changed (lambda instead of expression): custom helpers building `Expression<Func<SetPropertyCalls<T>,...>>` must be updated.

## Jumping to EF Core 11
- Needs .NET 11.
- **EF803** `UseSqlServer` now defaults to compatibility level 160 (SQL Server 2022) instead of 150. If prod runs SQL Server 2019 or an older compat level, set it explicitly: `UseSqlServer(cs, o => o.UseCompatibilityLevel(150))`.
- **EF804** Depends on Microsoft.Data.SqlClient 7.0, which removed the Azure/Entra ID auth dependencies from the core package. Apps using `Authentication=Active Directory ...` need to add the separate Azure auth package described in the EF 11 breaking-changes doc.
- **EF805** `EFOptimizeContext` MSBuild property removed: delete it from .csproj and use the current compiled-model approach.
- `SqlVector<T>` columns are no longer loaded in entity queries unless projected: code reading them after a normal query gets nothing.
- `Migrate()` on a DB with no migrations in the assembly changed behaviour (see doc).
- **EF806** Cosmos: Newtonsoft.Json replaced by System.Text.Json; `__jObject` shadow property removed, unmapped properties no longer preserved; undefined projections now throw. Document id escaping changed: check existing ids still resolve.
- SQL may change for LINQ you never touched (join pruning, CAST stripping): diff logged SQL for top queries.

## EF809 EF6 to EF Core readiness | info (report section)
Score each item, list blockers:
| Item | Blocker? | Notes |
|---|---|---|
| EDMX / Database First designer | yes | Re-scaffold with `dotnet ef dbcontext scaffold` or EF Core Power Tools |
| `ObjectContext` usage | yes | Rewrite to DbContext |
| Lazy loading everywhere (`virtual`) | medium | EF Core needs `UseLazyLoadingProxies` + package; better: remove reliance |
| `Database.SqlQuery<T>` / `ExecuteSqlCommand` | low | `SqlQuery<T>` (EF8+), `ExecuteSql` |
| Stored procs mapped via EDMX function imports | medium | `FromSql` / `SqlQuery<T>` / `ExecuteSql` |
| `DbConfiguration`, EF6 interceptors | medium | EF Core interceptors |
| Entity splitting, TPT, complex types | low | supported in modern EF Core (TPT 5+, entity splitting 7+, complex types 8+) |
| `System.Data.Entity` spatial | medium | NetTopologySuite |
| Many-to-many implicit join tables | low | supported 5+ |
| Group by behaviour, client eval | high | EF Core 3+ throws on untranslatable queries instead of silently evaluating in memory; every such query must be rewritten |
| .NET Framework app (WebForms, MVC5) | yes | EF Core 10/11 need modern .NET; WebForms cannot move. Option: keep EF6 6.5 on .NET Framework, or strangler-fig the data layer into a new .NET API |
Recommend side-by-side migration per bounded context, not big bang.

## EF810 Package hygiene
- Mixed EF Core package versions across projects (for example Core 8 + SqlServer 9): align with Central Package Management (`Directory.Packages.props`).
- `Microsoft.EntityFrameworkCore.Tools/Design` must match runtime version.
- Explicit old `Microsoft.Data.SqlClient` reference pinning below what EF needs.

## Upgrade plan template (put in report)
1. Pin current SQL: log SQL for the top 20 queries (by Query Store) on the current version.
2. Upgrade .NET + EF packages together, align all EF packages.
3. Fix compile errors, then go through breaking changes for each version jumped.
4. `dotnet ef migrations has-pending-model-changes`; add migration if needed and read it line by line.
5. Run tests (real DB). Diff SQL for the top 20 queries.
6. Load test the hot endpoints. Roll out behind a canary.
