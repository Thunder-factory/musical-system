from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('songs', '0008_generationjob_remote_result'),
    ]

    operations = [
        migrations.AddField(
            model_name='song',
            name='source_type',
            field=models.CharField(
                choices=[('generated', 'Generated'), ('uploaded', 'Uploaded')],
                default='generated',
                max_length=20,
            ),
        ),
    ]
