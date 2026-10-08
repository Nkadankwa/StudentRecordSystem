from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from accounts.models import User


class BackupTests(TransactionTestCase):
    def test_backup_is_readable_and_existing_files_are_preserved(self):
        User.objects.create_user(username='fictional-backup-user')
        with tempfile.TemporaryDirectory(prefix='srs-backup-test-', dir=settings.BASE_DIR) as folder:
            target = Path(folder) / 'snapshot.sqlite3'
            call_command('backup_sqlite', str(target), verbosity=0)
            with closing(sqlite3.connect(target)) as restored:
                self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(restored.execute('SELECT username FROM accounts_user').fetchone()[0], 'fictional-backup-user')
            original = target.read_bytes()
            with self.assertRaises(CommandError):
                call_command('backup_sqlite', str(target), verbosity=0)
            self.assertEqual(target.read_bytes(), original)
