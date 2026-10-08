# Student Record System

Django application for administrator setup, teacher score/attendance entry and
students viewing their own records. SQLite is the selected local database.

## Local setup (PowerShell)

Use Python 3.12 or newer. From the directory containing `manage.py`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Paste the generated key into your private `.env` as single-quoted `DJANGO_SECRET_KEY`.
Use `DJANGO_DEBUG=true` and `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1` locally. Then:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/accounts/login/ or `/admin/`. For this existing checkout,
`..\python.exe` can replace `.\.venv\Scripts\python.exe`. Reset a local password
interactively with `manage.py changepassword <username>`.
Start with an empty database; the custom user model cannot be retrofitted into a
database already migrated with Django's original User model.

## Configuration

`.env` loads automatically; process environment variables take precedence.
Actual credentials belong only in a private `.env` or deployment secret store.
Safe examples contain placeholders. Private keys, environments and SQLite files are ignored.

| Variable | Purpose / default |
| --- | --- |
| `DJANGO_SECRET_KEY` | Required generated secret; no default |
| `DJANGO_DEBUG` | `false`; explicitly enable for development |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts; explicit hosts required when debug is off |
| `DJANGO_TIME_ZONE` | `Asia/Shanghai`; timestamps stored with timezone awareness |
| `DB_ENGINE` | `sqlite`, or optional `mysql` |
| `DB_NAME` | SQLite path, default project `db.sqlite3`; required database name for MySQL |
| `DB_USER`, `DB_PASSWORD` | Private MySQL credentials; no credential defaults |
| `DB_HOST`, `DB_PORT` | MySQL server; defaults `127.0.0.1`, `3306` |
| `DEMO_PASSWORD` | Optional strong local demo password; otherwise generated |

MySQL requires separately installing `mysqlclient` and creating its database.
The performance/restore drill covers SQLite. See [production variables](docs/deployment.md).

## Roles and setup

| Role | Permissions |
| --- | --- |
| Student | Own profile, scores, attendance and printable record |
| Teacher | Students in assigned course/term combinations; entry and print for those combinations |
| Administrator | All application records; Django admin setup with staff status and model permissions |

Superusers must be administrators. Staff status alone does not grant a teacher
academic admin access. Assignment sections are labels; access operates by course
and term. Withdrawn enrolments are excluded from teacher rosters. Unauthorized
existing records return 403; missing records return 404.

In Django admin create accounts and matching profiles, then years, terms, courses,
teaching assignments, enrolments and assessments. Use `accounts.services.create_account`
for atomic account/profile creation in code. Resolve conflicting profiles before role changes.

## Workflows and sample data

- Students open **My profile**, **Scores**, **Attendance** and their printable record.
- Teachers and administrators search students by number/name prefix and filter records
  by course and term. **Enter or update scores** loads the assessment roster.
- Scores must be within the assessment maximum. Blank values preserve stored scores.
  Attendance requires an explicit status for every student and a date within the term.
  Existing session dates/labels remain unchanged when correcting attendance.
- All rows save in one transaction. Invalid or changed rosters cause no partial writes.
  Signed edit snapshots expire after one hour and reject stale edits while preserving input.
- **View printable record** combines permitted enrolments, scores and attendance totals.
  **Print record** opens browser printing with navigation and controls hidden.

Student lists contain 20 rows per page; record and edit-link lists contain 50.
Attendance totals cover all filtered records; individual print records are complete.
Entry forms support up to 1,000 roster rows.

With debug enabled, `python manage.py seed_demo` creates fictional
`demo-srs-student`, `demo-srs-teacher` and `demo-srs-administrator` accounts plus records.
It prints a generated password once unless `DEMO_PASSWORD` was supplied privately.
Repeat runs preserve data/passwords; conflicts are rejected. The command refuses
to run with debug off. Use a disposable development database, never production.

## Tests and project structure

```powershell
.\.venv\Scripts\python.exe manage.py test --noinput
.\.venv\Scripts\python.exe manage.py test tests.academics --noinput
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe tools/verify_performance.py
```

The benchmark creates/removes its own fictional database, measures common requests
and verifies a SQLite backup restore. See [operations and results](docs/operations.md).

| Directory | Responsibility |
| --- | --- |
| `config` | Settings, routing and production security |
| `accounts` | Custom user/profiles, authentication and authorization policies |
| `academics` | Periods, assignments, enrolments, scores, attendance and entry services |
| `student` | Scoped profiles and paginated student search |
| `management` | Reserved app package |
| `tests/accounts`, `tests/academics`, `tests/student`, `tests/management` | Tests grouped by application |
| `templates` | Shared HTML and app templates |
| `static/css` | All application and print styles |
| `tools` | Disposable performance/restore verification |

See [the data model](docs/domain-model.md). Bulk ORM writes bypass cross-table
validation; use entry services for academic records. Latest updater/timestamp
attribution is not a complete revision history.

## Deployment and contributions

Follow [deployment notes](docs/deployment.md) and [backup/restore steps](docs/operations.md).
Production settings have been checked locally; no live server has been deployed.

Use focused branches and commits describing the problem and resulting behavior.
Run relevant tests, system and migration checks before review. Include reviewed
migrations when models change. Review `git diff` and `git diff --cached` before
committing; exclude secrets, personal data, generated files and environments.
Git initialization is intentionally omitted.
