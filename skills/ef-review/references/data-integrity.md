# Transactions, concurrency, integrity (EF301 to EF305)

## EF301 Several SaveChanges in one business operation | medium | All
Two or more `SaveChanges` in one method with no transaction: if the second fails, the first is already committed.
**Fix**: single SaveChanges (EF wraps it in a transaction), or:
```csharp
await using var tx = await _db.Database.BeginTransactionAsync(ct);
// ... SaveChangesAsync x N
await tx.CommitAsync(ct);
```
If `EnableRetryOnFailure` is on, wrap the whole thing in `_db.Database.CreateExecutionStrategy().ExecuteAsync(...)`, otherwise user transactions throw.

## EF302 No concurrency handling | medium | All
RowVersion configured but no `catch (DbUpdateConcurrencyException)` anywhere, or no RowVersion on contested data (EF104).
**Fix**: catch, reload or merge, return 409 to the client. Send RowVersion to the UI and back on edits.

## EF303 No retry on transient errors (Azure SQL) | low | EF Core 1+ / EF6 6.0+
`UseSqlServer(...)` without `EnableRetryOnFailure()` when the app runs on Azure SQL (connection string has `database.windows.net`) or the user says cloud. EF Core: `UseAzureSql()` (EF Core 9+) sets sensible defaults. EF6: `SqlAzureExecutionStrategy` via `DbConfiguration`.

## EF304 Read-modify-write races | high | All
Patterns like `var stock = item.Qty; item.Qty = stock - n; SaveChanges` without a concurrency token, or "check then insert" for unique values without a unique index.
**Fix**: concurrency token, unique index + catch `DbUpdateException`, or atomic `ExecuteUpdate(s => s.SetProperty(i => i.Qty, i => i.Qty - n))` with a `Where(i => i.Qty >= n)` guard.

## EF305 Query filters bypassed
Global filters (soft delete, tenant) do not apply to raw SQL (`FromSql`), `ExecuteSql`, stored procs, or `IgnoreQueryFilters()`. Check each use. EF Core 10 named filters let you disable only the one you mean.

## Audit fields
If SaveChanges is overridden for audit/soft delete, `ExecuteUpdate/ExecuteDelete` (EF7+) skip it. Flag every ExecuteUpdate/Delete in a codebase with SaveChanges overrides or `SaveChangesInterceptor`s.
