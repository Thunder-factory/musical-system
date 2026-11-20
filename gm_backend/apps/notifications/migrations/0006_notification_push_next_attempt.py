from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0005_notification_push_delivery'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='push_next_attempt_at',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
