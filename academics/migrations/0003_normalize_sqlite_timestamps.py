from django.db import migrations


def normalize_timestamps(apps, schema_editor):
    """Keep instants unchanged, using the same SQLite format as normal ORM writes."""
    if schema_editor.connection.vendor != 'sqlite':
        return
    alias = schema_editor.connection.alias
    for name in ('Score', 'AttendanceRecord'):
        model = apps.get_model('academics', name)
        records = model.objects.using(alias).values('pk', 'created_at', 'updated_at')
        for row in records.iterator(chunk_size=500):
            model.objects.using(alias).filter(pk=row['pk']).update(
                created_at=row['created_at'], updated_at=row['updated_at'])


class Migration(migrations.Migration):
    dependencies = [('academics', '0002_assignments_scores_attendance')]
    operations = [migrations.RunPython(normalize_timestamps, migrations.RunPython.noop)]
