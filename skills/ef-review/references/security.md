# Security (EF005, EF401 to EF405)

## EF005 SQL injection in raw SQL | critical | All
Unsafe:
```csharp
_db.Users.FromSqlRaw($"SELECT * FROM Users WHERE Name = '{name}'");    // interpolation into Raw
_db.Users.FromSqlRaw("SELECT * FROM Users WHERE Name = '" + name + "'");
_db.Database.ExecuteSqlRaw("DELETE FROM T WHERE Id = " + id);
ctx.Database.SqlQuery<User>("... " + name);                           // EF6
ctx.Database.ExecuteSqlCommand("... " + name);                        // EF6
```
Safe:
```csharp
_db.Users.FromSql($"SELECT * FROM Users WHERE Name = {name}");         // EF Core 7+, parameterised
_db.Users.FromSqlInterpolated($"... {name}");                          // EF Core 3+
_db.Users.FromSqlRaw("... WHERE Name = {0}", name);
ctx.Database.SqlQuery<User>("... WHERE Name = @p0", new SqlParameter("@p0", name)); // EF6
```
Dynamic column/table names cannot be parameters: whitelist them.
EF Core ships analyzers (EF1001/EF1002) that warn on interpolated strings in Raw methods; make sure warnings are not suppressed.

## EF401 EnableSensitiveDataLogging in production | high
Logs parameter values (passwords, PII, payment data). Must be guarded:
```csharp
if (env.IsDevelopment()) options.EnableSensitiveDataLogging();
```
Same for `EnableDetailedErrors` (EF404, low).

## EF402 Secrets in code or committed config | critical (code) / high (appsettings)
Connection strings with `Password=`/`Pwd=` in `.cs`, `appsettings*.json`, `web.config` committed to git.
**Fix**: user-secrets for dev, Key Vault / environment variables for prod, Managed Identity (`Authentication=Active Directory Default`) for Azure SQL. Rotate any password already committed.

## EF403 IgnoreQueryFilters / tenant leaks | medium
Every `IgnoreQueryFilters()` in a multi-tenant or soft-delete app is a potential data leak. Check it is admin-only and still filters by tenant manually. EF Core 10: use named filters and ignore only the soft-delete one.

## EF405 Least privilege
App login should not be `db_owner` / `sa` in prod. If migrations run from the app (EF205) it needs DDL rights; another reason to run migrations from the pipeline.

## Mass assignment
Binding request bodies directly to entities then `Update(entity)` lets clients set any column (IsAdmin, TenantId, Price). Use DTOs and map allowed fields.
