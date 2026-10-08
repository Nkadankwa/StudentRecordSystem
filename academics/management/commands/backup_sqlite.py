"""Create a consistent SQLite snapshot without overwriting any existing file."""
import sqlite3
from contextlib import closing
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Back up SQLite to a new private file using the online backup API.'

    def add_arguments(self, parser):
        parser.add_argument('destination')

    def handle(self, *args, **options):
        if connection.vendor != 'sqlite':
            raise CommandError('This command supports SQLite only.')
        target = Path(options['destination']).expanduser().resolve()
        if not target.parent.is_dir():
            raise CommandError('Create the private destination directory first.')
        # Exclusive creation rejects the live database, symlinks and existing backups.
        try:
            with target.open('xb'):
                pass
        except OSError as error:
            raise CommandError('Destination must be a new writable file.') from error
        try:
            connection.ensure_connection()
            with closing(sqlite3.connect(target)) as snapshot:
                connection.connection.backup(snapshot)
                if snapshot.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise CommandError('Backup integrity check failed.')
        except Exception:
            target.unlink(missing_ok=True)
            raise
        self.stdout.write(self.style.SUCCESS('SQLite snapshot created and integrity checked.'))
