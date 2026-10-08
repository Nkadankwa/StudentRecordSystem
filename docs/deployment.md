# Production deployment

Use `DJANGO_SETTINGS_MODULE=config.production`, a production WSGI/ASGI server and
an HTTPS reverse proxy. Choose the server for your hosting environment; `runserver`
is for local development. No hosting provider or live deployment is configured.

Start from `.env.production.example`, supplying actual values privately.
Production forces debug off, requires explicit allowed hosts and a generated key
of at least 50 characters, and rejects insecure or wildcard trusted origins.
Keep the same key across workers and restarts.

| Variable | Behavior |
| --- | --- |
| `DJANGO_ALLOWED_HOSTS` | Actual hostname(s), without schemes; no wildcard |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Optional explicit HTTPS origins, comma-separated; no paths/wildcards |
| `DJANGO_HSTS_SECONDS` | Positive integer; default one year (31536000) |
| `DJANGO_TRUST_PROXY` | Default false; trusts `X-Forwarded-Proto` only when true |
| `SMTP_HOST`, `SMTP_PORT` | Optional SMTP service; localhost:587 default, STARTTLS |
| `SMTP_USER`, `SMTP_PASSWORD` | Optional private SMTP credentials |

SMTP replaces console mail to avoid printing message contents. Notifications are
deferred; configure/test delivery before adding an email workflow. Deployment
checks do not establish an SMTP connection.

HTTPS redirects, secure/HTTP-only cookies, frame denial, content sniffing protection
and same-origin referrer policy are enabled. HSTS includes subdomains and the
preload directive: all affected subdomains must support HTTPS before deployment.
This configuration does not submit a domain to a browser preload list.
Enable proxy trust only when the proxy strips client-supplied forwarding headers
and sets its own correct scheme. Block direct access to the application server.

## Checklist

- Install declared dependencies in an isolated environment; provision a private
  database accessible only to application/backup operators.
- Supply the real hosts, generated key and required origins privately; remove demo accounts.
- Verify live certificates, redirects, proxy behavior and HSTS prerequisites.
- Run tests, then with the production environment loaded:

  ```powershell
  python manage.py check --deploy --settings=config.production
  python manage.py migrate --settings=config.production
  python manage.py collectstatic --noinput --settings=config.production
  ```

- Serve `staticfiles/` through the web server; never expose databases, backups,
  `.env`, source files or private keys. Restrict admin access per operator policy.
- Schedule persistent backups and perform the [restore drill](operations.md).
- Verify login, role boundaries, CSRF, edits and printing on the deployed server.
- Set login rate limits at the trusted proxy if deployment requirements justify them.
  No extra lockout dependency was justified for the local application.

Authenticated responses use private/no-store cache headers. Django request,
security and server logs retain severity/status but remove request paths, bodies,
exception details and request objects. Configure proxy/server/platform logs
separately to avoid cookies, passwords, query strings and student data.

Deployment checks passed locally with a random key and synthetic hostname.
Live TLS, SMTP, hosting availability and MySQL behavior remain deployment checks.
