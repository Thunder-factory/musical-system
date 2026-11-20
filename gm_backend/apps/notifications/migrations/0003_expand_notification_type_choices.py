from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_alter_notification_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(
                choices=[
                    ('song_ready', 'Canción lista'),
                    ('song_failed', 'Canción fallida'),
                    ('karaoke_ready', 'Karaoke listo'),
                    ('karaoke_failed', 'Karaoke fallido'),
                    ('stem_ready', 'Stems listos'),
                    ('stem_failed', 'Separación fallida'),
                    ('humming_ready', 'Tarareo mejorado'),
                    ('humming_failed', 'Tarareo fallido'),
                    ('translation_ready', 'Traducción lista'),
                    ('translation_failed', 'Traducción fallida'),
                    ('mix_ready', 'Mix exportado'),
                    ('mix_failed', 'Mix fallido'),
                    ('faceswap_ready', 'Face swap listo'),
                    ('faceswap_failed', 'Face swap fallido'),
                    ('credit_grant', 'Créditos otorgados'),
                    ('credit_low', 'Créditos bajos'),
                    ('system', 'Sistema'),
                ],
                default='system',
                max_length=30,
            ),
        ),
    ]
