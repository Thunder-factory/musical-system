from django.db import migrations, models


def keep_one_owner_per_token(apps, schema_editor):
    UserDevice = apps.get_model('users', 'UserDevice')
    User = apps.get_model('users', 'User')

    token_ids = UserDevice.objects.values_list('token', flat=True).distinct()
    for token in token_ids:
        devices = list(
            UserDevice.objects.filter(token=token).order_by(
                '-is_active', '-last_seen_at', '-id'
            )
        )
        if not devices:
            continue
        owner = devices[0]
        UserDevice.objects.filter(token=token).exclude(id=owner.id).delete()
        User.objects.filter(fcm_token=token).exclude(id=owner.user_id).update(fcm_token=None)


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0003_userdevice'),
    ]

    operations = [
        migrations.RunPython(keep_one_owner_per_token, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='userdevice',
            name='unique_user_device_token',
        ),
        migrations.AddConstraint(
            model_name='userdevice',
            constraint=models.UniqueConstraint(
                fields=('token',),
                name='unique_fcm_token_owner',
            ),
        ),
    ]
