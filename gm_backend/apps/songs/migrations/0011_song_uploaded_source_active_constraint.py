from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('songs', '0010_song_uploaded_fingerprint'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='song',
            name='unique_uploaded_song_source',
        ),
        migrations.AddConstraint(
            model_name='song',
            constraint=models.UniqueConstraint(
                condition=Q(
                    source_sha256__isnull=False,
                    source_type='uploaded',
                    deleted_at__isnull=True,
                ),
                fields=('user', 'source_sha256'),
                name='unique_uploaded_song_source',
            ),
        ),
    ]
