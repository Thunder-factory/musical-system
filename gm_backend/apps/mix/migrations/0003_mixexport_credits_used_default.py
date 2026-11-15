from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('mix', '0002_mixproject_tags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mixexport',
            name='credits_used',
            field=models.IntegerField(default=0),
        ),
    ]
