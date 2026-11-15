from django.db import migrations, models


def reset_unfinished_credits(apps, schema_editor):
    StemJob = apps.get_model('stems', 'StemJob')
    StemJob.objects.exclude(status='completed').update(credits_used=0)


class Migration(migrations.Migration):
    dependencies = [
        ('stems', '0002_stemjob_remote_job_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='stemjob',
            name='source_sha256',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='stemjob',
            name='credits_used',
            field=models.IntegerField(default=0),
        ),
        migrations.RunPython(reset_unfinished_credits, migrations.RunPython.noop),
    ]
