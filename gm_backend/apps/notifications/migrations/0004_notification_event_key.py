from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_expand_notification_type_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='event_key',
            field=models.CharField(
                blank=True,
                default=None,
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name='notification',
            constraint=models.UniqueConstraint(
                condition=models.Q(event_key__isnull=False),
                fields=('user', 'event_key'),
                name='unique_notification_event_per_user',
            ),
        ),
    ]
