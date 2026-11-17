from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('songs', '0011_song_uploaded_source_active_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='generationjob',
            name='remote_job_id',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
