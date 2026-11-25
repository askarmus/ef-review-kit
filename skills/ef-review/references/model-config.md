# Model configuration (EF101 to EF108)

## EF101 decimal without precision | medium | EF Core 5+ (`HasPrecision`), EF6 (`HasPrecision` in fluent API)
EF Core warns and defaults to `decimal(18,2)`, so money/rates silently get truncated or rounded.
**Fix**: `[Precision(18, 4)]` or `.HasPrecision(18, 4)`; or globally in `ConfigureConventions` (EF Core 6+):
```csharp
protected override void ConfigureConventions(ModelConfigurationBuilder b)
{
    b.Properties<decimal>().HavePrecision(18, 4);
    b.Properties<string>().HaveMaxLength(256);
}
```

## EF102 string without max length | low | All
Every string becomes `nvarchar(max)`: can't be an index key column, larger memory grants, slower.
**Fix**: `HasMaxLength`, `[MaxLength]`, or a convention (above). Use `IsUnicode(false)` for ASCII codes to match `varchar` columns and avoid implicit conversions.

## EF103 Cascade delete review | high | All
Explicit `OnDelete(DeleteBehavior.Cascade)`, or required relationships (cascade by convention). Deleting one parent can wipe large child sets, and multi-path cascades fail on SQL Server.
**Check**: for each cascade, is deleting the children really intended? For business data prefer `Restrict` / `NoAction` + soft delete. EF6: `WillCascadeOnDelete(false)` or remove `OneToManyCascadeDeleteConvention`.

## EF104 No concurrency token on contested entities | medium | All
Entities edited by many users (orders, stock, balances, bookings) without `[Timestamp] byte[] RowVersion` / `IsRowVersion()` / `IsConcurrencyToken()`: last write wins silently.
**Fix**: add RowVersion, handle `DbUpdateConcurrencyException` (see data-integrity.md).

## EF105 Owned types where complex types fit | info | EF Core 8+ (complex types), 10+ (JSON complex types), 11 (TPT/TPC, keys/indexes)
Value objects (Address, Money) modelled with `OwnsOne`. Complex types have value semantics, no hidden key, and from EF 11 are the recommended alternative to owned entities.
```csharp
modelBuilder.Entity<Customer>().ComplexProperty(c => c.Address);           // EF8+, columns
modelBuilder.Entity<Customer>().ComplexProperty(c => c.Prefs, b => b.ToJson()); // EF10+, JSON
```
Migration needs care: check column names stay the same; generate the migration and read it.

## EF106 Enum storage | info | All
Enums stored as int are fine for performance but unreadable in the DB and fragile if values are reordered. Consider `.HasConversion<string>()` with a max length for readability, or document the values. Never reorder enum members without explicit numbers.

## EF107 Value conversions on query paths | medium | EF Core 2.1+
Filtering on a property with a value converter can block index use or fail to translate. Check queries that filter on converted properties.

## EF108 Temporal tables / audit | info | EF Core 6+ (temporal), 11 (period columns as normal properties)
If the team hand-rolls history tables, suggest SQL Server temporal tables: `ToTable(t => t.IsTemporal())`, query with `TemporalAsOf`.

## Checklist for manual review
- Keys: GUID PKs as clustered index? Suggest sequential GUIDs (`NEWSEQUENTIALID()` default or EF's sequential value generator) or int/long.
- Required vs nullable matches the DB (nullable reference types on).
- Global query filters (soft delete, tenant) applied to all relevant entities. EF Core 10: named filters `HasQueryFilter("SoftDelete", ...)` so one can be disabled without the other: `IgnoreQueryFilters(["SoftDelete"])`.
- Shadow FK properties created by accident (two navigations, wrong FK name): check the migration snapshot for `...Id1` columns.
- Seed data: EF Core 9+ `UseSeeding`/`UseAsyncSeeding` instead of `HasData` for non-static data.
