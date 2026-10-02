# Student Record System

Early Django scaffold with `config`, `accounts`, `management`, and `student` packages.
Shared templates live in `templates/`; CSS, JavaScript, and images in `static/`.
Currently only `/admin/` is routed.

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

Open http://127.0.0.1:8000/admin/. For the existing checkout, `..\python.exe`
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
Initial migrations and database setup are Day 5 work. Until those migrations are
created, the `migrate` and `createsuperuser` startup steps are not yet available.
Do not apply this custom-user change to a database already migrated with Django's
original user model; use a new development database for Day 5.

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
