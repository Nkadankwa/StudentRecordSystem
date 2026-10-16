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

For a populated dashboard, import the [fictional SQL dataset](data/README.md) with
`python manage.py load_sample_sql` after migrations. It adds 24 students, three
courses and linked scores/attendance, without preset passwords or changing existing records.
Administrator dashboards have direct setup links; teacher dashboards show assigned
rosters and entry actions; student dashboards show their own recent results and courses.

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

The frontend follows the supplied Stitch Academic Record Workspace design. See
[the design integration](DESIGN.md) for the shared shell, local assets, responsive
navigation and the boundary between working features and mockup-only content.
Teaching assignments and scoped rosters are at `/academics/assignments/`; the
administrator course catalog is at `/academics/catalog/`, and permission-aware
setup links are at `/accounts/setup/`.
Migration `academics.0003` normalizes legacy imported SQLite timestamps without
changing their instants, allowing imported scores and attendance to pass concurrent-edit checks.

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
See [the handover](docs/handover.md) and [release verification](docs/release-verification.md)
for acceptance evidence, the role demonstration and the historical credential finding.

To create a portable source archive without secrets or installed environments:

```powershell
python tools/package_release.py dist/StudentRecordSystem-release.zip
```

Extract the archive outside the old virtual-environment directory and follow the
local setup steps. The packaging command requires a new archive filename.

Use focused branches and commits describing the problem and resulting behavior.
Run relevant tests, system and migration checks before review. Include reviewed
migrations when models change. Review `git diff` and `git diff --cached` before
committing; exclude secrets, personal data, generated files and environments.
Git initialization is intentionally omitted.

### Updating the reference styles

The supplied HTML design uses precompiled local CSS. Normal Django startup
does not need Node.js. After changing its utility classes, rebuild with:

```powershell
cd tools/frontend
npm install
npm run build
cd ../..
```

All styles are in `static/css/`. The header, sidebar and administrator overview
are adapted directly from the supplied Stitch HTML, using database records.

### Personalize page layouts

Use **Edit layout** on the administrator, teacher and student dashboards, student
profiles, course catalog or setup page. Hide sections with their **Hide** button
or the visibility checkboxes. Remaining sections fill the available columns.
Click a summary card's heading to collapse it, or collapse/expand all summaries
from the layout controls. Hidden sections can be restored there at any time.
**Restore default layout** shows all sections and opens the summaries.

Choices save automatically to your account, separately for each page type,
and remain available after reloading or signing in on another device. They change
presentation only; existing record permissions and edit workflows still apply.
If saving fails, a visible message and **Retry saving** button appear.
Apply the `accounts.0003_workspace_layout` migration when updating another copy.
### Grading and resits

An administrator configures a separate rule for each course and academic term in **Grading & resits** (`/academics/grading/`). Choose the pass percentage, replacement / higher-score / weighted calculation, optional cap, and whether the rule is enabled. No pass threshold is assumed when a rule has not been configured.

Assigned teachers enter original scores and, for scores below that rule's threshold, a resit score. Original scores remain visible and calculated results carry a resit identifier. Saved resits retain their calculation rule and assessment maximum when a policy is changed later. An unsuccessful resit displays **Fail — course resit required** in the student's course overview and printable record; this academic warning does not change the enrolment lifecycle status.

### Submitted record corrections

Only assigned teachers can enter scores and attendance. Changing submitted records requires a reason. Changes apply immediately and appear in the administrator's **Record changes** inbox with the teacher, reason, and before/after values. Administrators can accept changes or revoke them with a review reason. Revocation restores the previous values only when no later edit conflicts; conflicting records remain untouched.

Administrators manage teaching assignments and grading rules and can read academic records, but cannot directly enter scores or attendance, including through Django admin. Apply migrations with `python manage.py migrate` when updating another installation.

