from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('credits', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreditReservation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('amount', models.PositiveIntegerField()),
                ('reference_id', models.UUIDField()),
                ('reference_type', models.CharField(max_length=30)),
                ('status', models.CharField(choices=[('reserved', 'Reserved'), ('confirmed', 'Confirmed'), ('released', 'Released')], default='reserved', max_length=20)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='credit_reservations', to='users.user')),
            ],
        ),
        migrations.AddConstraint(
            model_name='creditreservation',
            constraint=models.UniqueConstraint(fields=('user', 'reference_id', 'reference_type'), name='unique_credit_reservation_reference'),
        ),
    ]
