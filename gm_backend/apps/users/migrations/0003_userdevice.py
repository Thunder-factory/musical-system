from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_tokens(apps, schema_editor):
    User = apps.get_model('users', 'User')
    UserDevice = apps.get_model('users', 'UserDevice')

    for user in User.objects.exclude(fcm_token__isnull=True).exclude(fcm_token='').iterator():
        UserDevice.objects.get_or_create(
            user_id=user.pk,
            token=user.fcm_token,
            defaults={
                'platform': 'unknown',
                'is_active': True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_user_fcm_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.TextField()),
                ('platform', models.CharField(choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web'), ('unknown', 'Unknown')], default='unknown', max_length=20)),
                ('device_id', models.CharField(blank=True, default='', max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('last_seen_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='devices', to='users.user')),
            ],
        ),
        migrations.AddConstraint(
            model_name='userdevice',
            constraint=models.UniqueConstraint(fields=('user', 'token'), name='unique_user_device_token'),
        ),
        migrations.AddIndex(
            model_name='userdevice',
            index=models.Index(fields=['user', 'is_active'], name='users_userde_user_id_5f8d2c_idx'),
        ),
        migrations.RunPython(migrate_legacy_tokens, migrations.RunPython.noop),
    ]
