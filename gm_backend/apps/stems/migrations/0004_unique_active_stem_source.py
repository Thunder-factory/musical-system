from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('stems', '0003_stemjob_hash_and_credits'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='stemjob',
            constraint=models.UniqueConstraint(
                condition=Q(status__in=['queued', 'processing']),
                fields=('user', 'source_sha256'),
                name='unique_active_stem_source',
            ),
        ),
    ]
