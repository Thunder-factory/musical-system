from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('songs', '0007_merge_20260620_1027'),
    ]

    operations = [
        migrations.AddField(
            model_name='generationjob',
            name='remote_result',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
