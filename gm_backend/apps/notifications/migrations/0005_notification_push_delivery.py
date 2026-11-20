from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_notification_event_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='push_attempts',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='notification',
            name='push_claimed_at',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='push_sent_at',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='push_last_error',
            field=models.TextField(blank=True, default=''),
        ),
    ]
