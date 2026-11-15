from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('songs', '0009_song_source_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='song',
            name='source_sha256',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name='song',
            constraint=models.UniqueConstraint(
                condition=Q(source_sha256__isnull=False, source_type='uploaded'),
                fields=('user', 'source_sha256'),
                name='unique_uploaded_song_source',
            ),
        ),
    ]
