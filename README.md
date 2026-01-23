# Student Record System

Early Django scaffold. The project package is `config`; domain apps are
`management` and `student`. Shared HTML templates go in `templates/` and CSS,
JavaScript, and images go in `static/`. Currently only `/admin/` is routed.

## Local startup (PowerShell)

From the directory containing `manage.py`, create an environment and install Django
(Python 3.12 or newer):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install "Django==6.1"
.\.venv\Scripts\python.exe manage.py check --settings=config.local
.\.venv\Scripts\python.exe manage.py migrate --settings=config.local
.\.venv\Scripts\python.exe manage.py createsuperuser --settings=config.local
.\.venv\Scripts\python.exe manage.py runserver --settings=config.local
```

Open http://127.0.0.1:8000/admin/. `config.local` uses a local SQLite database.
For this existing checkout, `..\python.exe` can replace
`.\.venv\Scripts\python.exe` to use the already installed environment.

The original `config.settings` still uses MySQL. To use it, install `mysqlclient`,
create the configured database, and update its connection settings before running
the same commands without `--settings=config.local`.

The domain models do not yet have initial migrations. Generate those when the
planned account and profile schema is ready, before migrating domain data.
