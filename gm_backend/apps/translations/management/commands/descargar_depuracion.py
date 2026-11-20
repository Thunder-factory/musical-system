"""Descarga los archivos intermedios de un trabajo de traducción hecho con TRANSLATION_DEBUG=true.

Uso (dentro del contenedor del backend):
    python manage.py descargar_depuracion <id del trabajo o sus primeros caracteres> [--destino carpeta]

Por defecto se guardan en depuracion/<id>/ (en el host: gm_backend/depuracion/<id>/).
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.translations.models import TranslationJob
from ml.storage_client import get_storage_bucket, get_storage_client


class Command(BaseCommand):
    help = 'Descarga de R2 los archivos de depuración (translations/<trabajo>/debug/) de una traducción.'

    def add_arguments(self, parser):
        parser.add_argument('trabajo', help='ID del TranslationJob (basta con los primeros caracteres)')
        parser.add_argument('--destino', default='depuracion', help='carpeta donde guardar (por defecto depuracion/)')

    def handle(self, *args, **options):
        prefijo_id = options['trabajo'].strip().lower()
        candidatos = [j for j in TranslationJob.objects.exclude(remote_job_id=None).order_by('-created_at')
                      if str(j.id).startswith(prefijo_id)]
        if not candidatos:
            raise CommandError(f'No hay ningún trabajo enviado a Modal cuyo id empiece por «{prefijo_id}».')
        if len(candidatos) > 1:
            raise CommandError('Varios trabajos coinciden; escribe más caracteres del id: '
                               + ', '.join(str(j.id) for j in candidatos[:5]))
        job = candidatos[0]
        prefijo = ((job.details or {}).get('debug') or {}).get('prefijo') or f'translations/{job.remote_job_id}/debug/'

        client, bucket = get_storage_client(), get_storage_bucket()
        claves = []
        for pagina in client.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=prefijo):
            claves += [o['Key'] for o in pagina.get('Contents', [])]
        if not claves:
            raise CommandError(f'No hay archivos de depuración en {prefijo} '
                               '(¿el trabajo se hizo con TRANSLATION_DEBUG=true?).')

        destino = Path(options['destino']) / str(job.id)
        destino.mkdir(parents=True, exist_ok=True)
        for clave in sorted(claves):
            ruta = destino / clave[len(prefijo):]
            client.download_file(bucket, clave, str(ruta))
            self.stdout.write(f'  {ruta.name} ({ruta.stat().st_size / 1e6:.1f} MB)')
        self.stdout.write(self.style.SUCCESS(f'{len(claves)} archivos en {destino.resolve()}'))
