# Migrations and schema (EF201 to EF208)

Review the last ~10 migrations plus anything not yet applied to production (ask the user which migration prod is on).

## EF201 Destructive operation | critical
`DropColumn`, `DropTable`, `DropIndex` on unique constraints, `DeleteData`.
**Check**: is data copied elsewhere first? Is this a rename that EF generated as drop+add (happens when you rename a property and EF cannot tell)? If so, replace with `RenameColumn`.

## EF202 Rename | high
`RenameColumn`/`RenameTable`: fine for the DB, but breaks old app instances during rolling deploys, plus raw SQL, views, reports and stored procs that use the old name. Suggest expand/contract: add new, dual write, backfill, switch reads, drop old.

## EF203 AlterColumn | medium
Shrinking length, changing type, nullable to not-null. Can fail on existing data or take long locks on big tables.
**Check**: not-null without `defaultValue` on a table with rows; type narrowing. Big tables: run off-hours, or batch backfill first.

## EF204 Raw SQL in migrations | low
`migrationBuilder.Sql(...)`. Review for idempotency, provider-specific syntax, and huge UPDATEs in one transaction (log growth). Batch large data fixes.

## EF205 Migrate() at app startup | medium
`Database.Migrate()` / `MigrateAsync()` in Program.cs. Problems: several instances race, app needs DDL rights, failed migration = app won't boot.
**Better**: run in the pipeline with `dotnet ef migrations script --idempotent` or migration bundles (`dotnet ef migrations bundle`, EF Core 6+). EF Core 9+ takes a lock when migrating, but separating still wins.
**EF Core 9+**: `Migrate()` throws `PendingModelChangesWarning` if the model has changes without a migration. Add a CI check: `dotnet ef migrations has-pending-model-changes` (EF Core 8+).

## EF206 EnsureCreated in production code | high
`EnsureCreated()` bypasses migrations; the DB can never be migrated afterwards. Only for tests/prototypes.

## EF207 Index creation on big tables | medium
`CreateIndex` on large tables blocks writes. SQL Server Enterprise/Azure: use `ONLINE = ON` via raw SQL or annotation (`.IsCreatedOnline()` on SQL Server provider, EF Core 7+).

## EF208 Migration hygiene
- Model snapshot conflicts after merges: EF Core 11 records the latest migration ID in the snapshot, so divergent branches show up as a merge conflict instead of silent breakage.
- Migrations folder edited after being applied: never edit an applied migration, add a new one.
- Missing `Down()` or `Down()` that would lose data: document that rollback = restore.
- Data seeding in migrations that depends on current entity classes (breaks when classes change): use raw SQL in the migration instead.

## Tooling wins by version
- EF Core 6+: migration bundles.
- EF Core 8+: `has-pending-model-changes`.
- EF Core 11: `dotnet ef database update --add` (create + apply in one step, good for dev), `.config/dotnet-ef.json` defaults, `--context "*"` for all contexts, `-NoBuild` in PMC, CLI logs to stderr so scripts on stdout are clean, `ExcludeForeignKeyFromMigrations()` to keep a relationship but skip the DB constraint.

## Testing migrations
Suggest a CI job that spins up SQL Server (Testcontainers) and applies all migrations from empty, then applies the latest against a copy of prod schema if possible.
