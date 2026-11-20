# Despliegue de MusicAI en la VM de Azure (demo)

Pensado para una **presentación corta** (unos días). La app corre igual que en desarrollo (Django `runserver` + Vite),
con **Caddy delante dando HTTPS** para que funcionen el micrófono del tarareo, "copiar código" de las salas y el push.
Las IA siguen en **Modal**, los archivos en **R2** y las salas en **Firebase**: la VM no necesita GPU.

| Pieza | Valor |
|---|---|
| VM | Azure B2as v2 (2 vCPU, 8 GB), Ubuntu, usuario `Leonardo` |
| Acceso | `ssh -i ~/claves/SI2Proyecto_key.pem Leonardo@68.211.88.211` |
| Carpeta | `~/musical-system` |
| URL | `https://<APP_DOMAIN>` (subdominio de DuckDNS apuntando a la IP de la VM) |
| Puertos públicos | solo 80 y 443 (Caddy) |

## Archivos de esta carpeta
- `docker-compose.azure.yml`: se usa **junto** con el `docker-compose.yml` del repo. Quita los puertos públicos de backend y frontend, agrega Caddy, usa torch CPU y `restart: unless-stopped`.
- `Dockerfile.backend`: backend y workers de Celery con torch CPU.
- `Caddyfile`: HTTPS automático y proxy al frontend (que reenvía `/api` al backend).

## Comando base (en la VM, dentro de `~/musical-system`)
```bash
alias musicai='docker compose -f docker-compose.yml -f deploy/azure/docker-compose.azure.yml'
```

## Prender, apagar, ver
```bash
musicai up -d --build        # prender (la 1.ª vez construye imágenes: 10-20 min)
musicai ps                   # estado de los contenedores
musicai logs -f backend      # logs (también: celery-worker, celery-humming, tarareo, caddy)
musicai stop                 # apagar sin borrar nada
musicai start                # volver a prender lo apagado
musicai down                 # apagar y quitar contenedores (los datos de Postgres quedan en el volumen)
```

## Primera vez (resumen)
1. Crear el subdominio en https://www.duckdns.org apuntando a la IP de la VM.
2. Copiar el código a `~/musical-system` (por ejemplo `git archive` desde una PC con acceso al repo).
3. Copiar el `.env` (no está en el repo) y ajustar:
   - `APP_DOMAIN=<subdominio>.duckdns.org`
   - `DEV_ALLOWED_HOSTS` → agregar el dominio
   - `DEV_CORS_ALLOWED_ORIGINS` → agregar `https://<dominio>`
   - `DEV_STRIPE_SUCCESS_URL` / `DEV_STRIPE_CANCEL_URL` → `https://<dominio>/...`
   - `DJANGO_SECRET_KEY` nuevo y, si se quiere, `SUPERADMIN_PASSWORD` nuevo
4. (Opcional) Restaurar la base de la PC para conservar canciones, plantillas y usuarios:
   `musicai up -d postgres`, luego `pg_restore --clean --if-exists` del dump, y después `musicai up -d --build`.
5. Abrir 80 y 443 en el grupo de seguridad de red (NSG) de la VM en Azure.
6. `musicai up -d --build` y entrar a `https://<dominio>`. Caddy tarda unos segundos en sacar el certificado la primera vez.

## Notas
- Al arrancar, el backend corre `migrate` y el seed (crea admin y `cliente1..40`). El seed **vuelve a fijar los planes y la contraseña del admin** en cada arranque.
- Si cambias `tailwind.config.js`, reinicia el frontend (`musicai restart frontend`): Vite cachea el config.
- Costos: todo lo de IA usa la cuenta de Modal configurada en el `.env`. Ver `https://modal.com/usage`. Freno de emergencia: `modal app stop gm-music-server --yes`.
- RAM: con todo prendido usa unos 3-4 GB. Ver con `docker stats --no-stream`.
