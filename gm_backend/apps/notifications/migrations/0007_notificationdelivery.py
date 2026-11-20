from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0006_notification_push_next_attempt'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('sent', 'Enviada'), ('permanent_failure', 'Fallida permanentemente')], default='pending', max_length=24)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('claimed_at', models.DateTimeField(blank=True, default=None, null=True)),
                ('next_attempt_at', models.DateTimeField(blank=True, default=None, null=True)),
                ('sent_at', models.DateTimeField(blank=True, default=None, null=True)),
                ('last_error', models.TextField(blank=True, default='')),
                ('notification', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='notifications.notification')),
            ],
        ),
        migrations.AddConstraint(
            model_name='notificationdelivery',
            constraint=models.UniqueConstraint(fields=('notification', 'token'), name='unique_notification_delivery_token'),
        ),
    ]
