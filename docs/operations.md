# Performance and SQLite operations

## Repeatable benchmark

Run `python tools/verify_performance.py` from the project root; optionally pass
`--output <report.json>`. It creates a temporary directory inside the project,
builds a fresh fictional database, and removes it. Its database/secret settings
are overridden before Django starts; it never opens your configured database.

Dataset: 100 students, five courses, two terms, ten assignments and 1,000 each
of enrolments, scores and attendance records. Accounts have unusable passwords.
Teacher requests use Django's test client with one warmup and three timed samples.

| Request | Median seconds | Queries |
| --- | ---: | ---: |
| Student prefix lookup | 0.0121 | 4 |
| Score summary | 0.0281 | 8 |
| Attendance summary | 0.0396 | 9 |

Measured on Windows, Python 3.14.0, Django 6.1, local SQLite on 2026-10-05.
See [machine-readable results](performance-results.json). All samples met the
two-second target and 15-query budget. Measurements exclude network/proxy time
and concurrent production load; rerun on deployment hardware.

Related objects use `select_related`; authorization uses scoped queries.
Foreign-key/unique indexes and existing name indexes cover common lookup paths.
Case-insensitive prefix index usage depends on collation. The benchmark did not
justify additional indexes. Student pages have 20 rows; record/edit-link pages
have 50. Totals cover full filtered results; individual print records are complete.

## Back up SQLite

Backups contain personal information and password hashes. Create a private
directory outside web/static roots, restrict operator access, and use encrypted
storage and an explicit retention schedule. Store configuration secrets separately.
Use a new filename each time:

```powershell
python manage.py backup_sqlite 'C:\private-backups\srs-YYYYMMDD.sqlite3'
```

The directory must exist. The command uses SQLite's online backup API and runs
`PRAGMA integrity_check`. It refuses to overwrite any existing file, including
the live database. Add `--settings=config.production` when needed. Schedule it
with platform tools and monitor failures.

## Restore

1. Verify the backup's integrity with SQLite tooling. Preserve a separate rollback
   snapshot and match source/migration versions to the backup. Keep the existing secret privately available.
2. First copy the backup to a new private path in a disposable environment and set
   `DB_NAME` to that path. Run checks, inspect migration state, verify counts and role workflows.
3. Stop all workers/jobs that can write before switching the live database.
   Resolve WAL state with SQLite tooling while the original database is accessible;
   never combine a backup with unrelated WAL/SHM files.
4. Point `DB_NAME` at the verified restored file, confirm permissions and restart.
   Verify login and record reads/writes; retain rollback material until acceptance.
   Apply newer migrations only as a reviewed upgrade.

The verification tool snapshots its fictional database, restores to a new file,
checks integrity and student/score/attendance counts, reopens it through Django,
and serves the score page. The drill passed; no local or production database was restored.
This backup command supports SQLite only.

SQLite serializes writes; competing writes can fail safely and require a reload.
Entry snapshots reject stale submissions and expire after one hour. Conflicting
edits are not merged automatically, and there is no full historical audit ledger.
