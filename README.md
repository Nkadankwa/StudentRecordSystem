# Student Record System

Early Django scaffold with `config`, `accounts`, `management`, and `student` packages.
Shared templates live in `templates/`; CSS, JavaScript, and images in `static/`.
Sign in at `/accounts/login/`. The root URL redirects signed-in users to their
role home; Django admin remains at `/admin/`.

## Local startup (PowerShell)

Use Python 3.12 or newer. From the directory containing `manage.py`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Paste the generated key into `.env` as `DJANGO_SECRET_KEY` and keep it in single
quotes so special characters remain literal. Then run:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/accounts/login/ (or `/admin/` for staff administration). For the existing checkout, `..\python.exe`
can replace `.\.venv\Scripts\python.exe` to use the installed environment.
Do not share or commit `.env` or your local database.

## Configuration

`.env` loads automatically; existing process environment variables take precedence.
`.env.example` contains placeholders only. A real secret key is required, and debug
is disabled unless explicitly enabled. Standard commands use `config.settings`;
`config.local` remains a compatibility alias with the same behavior.

| Variable | Purpose / default |
| --- | --- |
| `DJANGO_SECRET_KEY` | Required generated private key; no default |
| `DJANGO_DEBUG` | `false`; use `true` for local development |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts; explicit hosts required when debug is off |
| `DJANGO_TIME_ZONE` | `Asia/Shanghai`, the local display time zone; timestamps use UTC with `USE_TZ=True` |
| `DB_ENGINE` | `sqlite` (default) or `mysql` |
| `DB_NAME` | SQLite file path (default: project `db.sqlite3`); required database name for MySQL |
| `DB_USER`, `DB_PASSWORD` | MySQL credentials; user required, no credential defaults |
| `DB_HOST`, `DB_PORT` | MySQL server, default `127.0.0.1:3306` |

SQLite needs no database server. For MySQL, install `mysqlclient`, create the
database separately, set `DB_ENGINE=mysql`, and fill in the MySQL variables shown
in `.env.example`. MySQL is optional and is not included in base requirements.

These settings cover the current development scaffold. Production security and
deployment settings are scheduled for a later stage.

## Schema status

Day 4 introduces `accounts.User` as `AUTH_USER_MODEL` before initial migrations.
Day 5 adds `accounts/migrations/0001_initial.py`. A clean database can now run
all migrations, including the custom user and profiles. Do not apply this
custom-user change to a database already migrated with Django's original user
model; use a new development database.

## Accounts and profiles

`User` extends Django's `AbstractUser` and stores username, hashed password,
first/last names, email, and a role: student, teacher, or administrator. Role values
are constrained in the database. Roles describe the user; Django staff flags and
permissions still control admin access. Superusers must be administrators.

`StudentProfile` links one-to-one to a student user and stores student number,
date of birth, nationality, and gender. Age is calculated from date of birth.
`TeacherProfile` links one-to-one to a teacher user and stores employee number.
Administrators use `User` directly. The old standalone Student, Teacher, and
Administrator models were replaced before migrations existed.

Profile creation is explicit, with no signals. Application code should use
`accounts.services.create_account` to create a user and required profile together
in a transaction. In Django admin, create the user first, then its matching
profile. Profile forms reject the wrong role, and user forms reject role changes
that conflict with an existing profile. Direct ORM writes must follow the same
validation policy (`full_clean` before saving); cross-table role consistency is
not a database constraint. Role changes require removing the previous profile
before creating the replacement, so they should be planned explicitly.


## Tests and local administrator

```powershell
.\.venv\Scripts\python.exe manage.py test accounts
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

If a local administrator already exists, set its password interactively with
`manage.py changepassword` followed by that account's username. A fresh checkout
should follow the `createsuperuser` step in the startup section.
Local `.env` and SQLite files are ignored and are not part of the source files.

## Authentication

- `/accounts/login/` accepts username and password, with CSRF protection and
  neutral invalid-credential messages.
- Successful login sends students, teachers, and administrators to their
  respective protected home pages. Each role can access only its own home.
- A safe same-site `next` URL is honored for returning to a protected page;
  external destinations are rejected. The destination still enforces its role.
- Sign out uses a CSRF-protected POST to `/accounts/logout/`; GET does not log out.
- The shared layout includes navigation, sign-in messages, and role dashboards.
  Academic dashboard sections are placeholders for future work.

## Secrets

Application secrets and database credentials come from `.env` or environment
variables. Never put actual passwords, tokens, or private key contents into
Python, templates, examples, or documentation. `.env.example` uses placeholders;
`.env` and common private-key files are ignored. No private key is required by
this authentication flow. Test accounts are synthetic, and test passwords are
generated at runtime. The fast test-only password hasher does not change the
application's default password hashing.


## Shared interface

All public account pages use `templates/base.html`. Navigation shows the signed-in
user's own dashboard. The Administration link appears only for staff users with
the administrator role; server-side access checks remain in place.
Student, teacher, and administrator dashboards have separate templates. Future
academic features are marked as planned rather than presented as working links.

Custom 403, 404, and 500 pages give a safe recovery link. For local diagnosis,
Django's detailed debug pages take precedence for 404/500 errors when
`DJANGO_DEBUG=true`; custom production errors are tested with debug disabled.
The stylesheet supports narrow screens, keyboard focus, and a skip-to-content link.


## Day 8 review checkpoint

The full 34-test suite and Django system checks pass, and migration checks report
no pending model changes. Tests cover account/profile relationships, role
constraints, transactional rollback, login/logout, CSRF, role-specific pages,
error templates, and isolated configuration defaults and failure cases.

Account creation now runs Django's configured password validators before saving;
`password=None` explicitly creates an account with no usable password.
Private `.env` and SQLite files are ignored. Previously tracked IDE files and
Python caches were removed from the Git index while preserving local copies.
The audit checks the current index and source files, not historical commits.

The checkpoint changes remain uncommitted; no tag was created. Production
security settings and deployment verification remain scheduled for Day 25.


## Academic setup (Day 9)

Django admin now supports academic years, terms, and courses under Academics.
Sign in with a staff account that has the appropriate model permissions, or a
local superuser. Create a year before its terms; courses can be created separately.
Search and filters are available on all three admin lists.

Year names are unique. Term names are unique within their year, and term dates
must fall within that year. End dates must be after start dates. Editing a year
cannot move its boundaries past existing terms, and a year with terms cannot be
deleted. Years sort newest first; terms sort chronologically.

Course codes are trimmed, uppercased, and validated for uniqueness by admin/model
validation; courses sort by code. Courses have a title, optional description, and
an active flag. For direct ORM writes, call `full_clean()` before `save()` to apply
normalization and cross-model validation. `save()`/bulk operations do not enforce
term containment or code normalization automatically; database constraints still
enforce date order and stored-value uniqueness.

The reviewed `academics/0001_initial.py` migration is applied to the local SQLite
database. The full suite now contains 48 passing tests, including academic admin
creation and rejection of invalid periods. No sample academic records were added
to the development database; fixture data exists only in tests.


## Assignments, scores, and attendance (Days 10–12)

The Academics admin now supports teaching assignments and enrolments, assessments
and scores, and attendance sessions and records. Configure years, terms, courses,
and account profiles first, then assignments and enrolments. No real student
records or sample data were inserted into the development database.

Assignments link a teacher profile to a course and term, with an optional section.
Duplicate assignments (including the section) and duplicate student/course/term
enrolments are rejected. Enrolment statuses are active, completed, and withdrawn.
Sections label assignments; enrolment and teacher access are scoped by course and
term, not by section.

Assessments use decimal maximum scores and percentage weights (0–100). Maximum
scores must be positive; submitted scores must be between zero and that maximum.
Students need a non-withdrawn enrolment in the assessment's course and term.
There is one score per student/assessment. Maximum scores cannot be reduced below
existing results, and assessments with scores cannot change course or term.

Attendance sessions include course, term, assigned teacher, date, and optional
lesson label. Dates must be within the term. Distinct lesson labels allow multiple
sessions on the same course/date; identical course/term/date/label sessions are
rejected. There is one record per student/session, with present, absent, late, or
excused status. Students need a non-withdrawn enrolment in the session's course
and term. Sessions with records cannot change course or term.

Score and attendance saves require an active administrator or a teacher assigned
to that course and term as `updated_by`. Admin derives this identity from the
signed-in user rather than a submitted form value. Creation and update timestamps
and the latest updater provide attribution; this is not a complete revision log.

Normal `save()` calls on these six new models run `full_clean()` automatically.
Bulk writes and queryset `update()` bypass cross-table model validation and should
not be used for application record entry. Database constraints still enforce
uniqueness, status choices, nonnegative scores, and assessment maximum/weight
bounds. Cross-table limits (such as a score's assessment maximum) are model rules.

The reviewed `academics/0002_assignments_scores_attendance.py` migration is applied
locally. All 65 tests pass, including admin attribution, duplicates, invalid ranges,
enrolment eligibility, teacher assignment, and record update timestamps. The
student/teacher record pages and their broader authorization policies are later
schedule items; dashboard placeholders remain until those workflows are built.


## Fictional demo data (Day 13)

With `DJANGO_DEBUG=true`, run `..\python.exe manage.py seed_demo`. It creates three
clearly fictional users (`demo-srs-student`, `demo-srs-teacher`, and
`demo-srs-administrator`) plus linked academic records. The administrator gets
account and academic model permissions. No existing accounts are reset or deleted.
Repeat runs preserve records and passwords; partial or conflicting demo account
names are rejected. If you manually alter/delete the demo records, inspect them
rather than expecting the command to repair them. All writes are transactional.

Set `DEMO_PASSWORD` in your ignored `.env` if you want to choose a strong local
demo password. Otherwise the command generates and prints a random development
password once. Keep it local; never use demo accounts in production. The command
refuses to run with debug disabled. The command was verified on disposable test
databases; it has not populated this checkout's development database.

## Student profiles and search (Days 14–17)

Students open their profile via My profile. Teachers use Assigned students;
administrators use Students. Direct URLs are `/students/me/`, `/students/`, and
`/students/<profile-id>/`. Teachers see only non-withdrawn students assigned to them
in the same course and term. Students cannot browse the list or another profile.
Unauthorized authenticated requests return 403; missing profiles return 404.

Search matches the beginning of student number, first name, or last name without
case sensitivity. Queries are limited to 100 characters; invalid input shows an
error and no records. Lists contain 20 students per page, with safe empty states.
Name indexes were migrated locally; backend collation affects index usage.
See [the domain diagram and review](docs/domain-model.md) for schema constraints,
access boundaries, and limitations. These pages do not yet display attendance or
scores; those record workflows follow in subsequent schedule days.

Days 13–17 verification: all 83 tests pass on a freshly migrated test database.
Django checks and migration checks pass. Student list/profile rendering was
verified at desktop and mobile widths. Demo seeding was exercised only in tests.
