# ef-review-kit

Claude Code plugin that reviews Entity Framework code (EF6 and EF Core 3 to 11):

- **Wrong usage and bugs**: N+1, client-side filtering, SaveChanges in loops, blocking async, DbContext lifetime, parallel use
- **Slow queries**: unbounded loads, non-sargable predicates, cartesian Includes, tracking, large Contains, plus SQL Server Query Store analysis
- **Model and migrations**: decimal precision, nvarchar(max), cascade deletes, concurrency tokens, destructive migrations, Migrate() at startup
- **Integrity and security**: transactions, retries, SQL injection, sensitive logging, secrets, query filter bypass
- **Memory, architecture, testing, observability**: hosted services, pooling, generic repositories, InMemory tests, query tags, slow query logging
- **New features and upgrade readiness**: version-aware suggestions (ExecuteUpdate, LeftJoin, FullJoin, MaxBy, complex types, named filters) and breaking changes up to EF Core 11, EF6 to EF Core readiness
- **Output**: report with health score (0 to 100), top 10 fixes, before/after code, benchmark plan; optional auto-fix

## Install

From GitHub (after you push this folder as a repo):
```
/plugin marketplace add <your-github-user>/ef-review-kit
/plugin install ef-review-kit@ef-review-kit
```
Local:
```
/plugin marketplace add /path/to/ef-review-kit
/plugin install ef-review-kit@ef-review-kit
```
Skill only (no commands): copy `skills/ef-review` to `~/.claude/skills/ef-review` or `<repo>/.claude/skills/ef-review`.

Needs Python 3.8+ (no packages) for the scanner.

## Use

| Command | What it does |
|---|---|
| `/ef-review [path] [--fix]` | Full review, writes `ef-review-report.md` |
| `/ef-slow [path]` | Slow query focus, optional Query Store analysis |
| `/ef-upgrade [10\|11] [path]` | Upgrade readiness and breaking changes |

(Plugin commands may show as `/ef-review-kit:ef-review` etc.)
Or just ask: "review the EF code in this repo", "find slow EF queries", "are we ready for EF Core 11?".

Run the scanner by hand:
```bash
python3 skills/ef-review/scripts/detect_ef.py <repo>
python3 skills/ef-review/scripts/scan.py <repo> --format md --out ef-scan.md
python3 skills/ef-review/scripts/scan.py <repo> --target-version 11 --format json --out ef-scan.json
```
Flags: `--ef-version N` (force; 6 = EF6), `--target-version N` (upgrade rules), `--include-tests`, `--max-per-rule N`.

## How it works

1. `detect_ef.py` reads .csproj / packages.config / Directory.Packages.props: EF flavour, version, providers, target framework, support status.
2. `scan.py` finds **candidates** with ~60 rules (EF001 to EF810) using comment/string-aware parsing and brace matching. Rules are version-aware per project (mixed EF6 + EF Core solutions work).
3. Claude verifies every candidate by reading the code, drops false positives, does the manual checks in `references/`, and writes the report.
4. Slow query mode uses `scripts/query_store.sql` (read-only) to map the worst production queries back to LINQ.
5. Fix mode applies chosen fixes one at a time and builds/tests after each batch.

## Rule IDs

| Range | Area |
|---|---|
| EF001-EF018 | Wrong usage, bugs, query performance |
| EF101-EF108 | Model configuration |
| EF201-EF208 | Migrations and schema |
| EF301-EF305 | Transactions, concurrency, integrity |
| EF401-EF405 | Security |
| EF501-EF505 | Memory and connections |
| EF601-EF607 | Architecture, testing, observability |
| EF701-EF708 | New features (modernisation) |
| EF801-EF810 | Upgrade readiness |

## Safety

- Never runs write/DDL SQL. Query Store script is read-only.
- Secrets are masked in findings.
- Schema changes go in new migrations, never edits to applied ones.

## Limits

The scanner is regex-based, not Roslyn. Expect some false positives (marked `confidence: low`) and misses for logic spread across files. That is why Claude verifies each hit. A Roslyn analyzer version is a possible v2.
