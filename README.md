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
