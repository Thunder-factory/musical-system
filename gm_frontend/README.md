# MusicAI — Frontend

Interfaz web de **MusicAI**, desarrollada con React, TypeScript y Vite. Incluye generación musical, biblioteca, Karaoke, salas colaborativas, separación de stems, Mix DJ, playlists, comunidad, pagos y administración.

## Stack

| Tecnología | Uso |
| :--- | :--- |
| React 19 + TypeScript | Interfaz y tipado estático |
| Vite 8 | Desarrollo y build de producción |
| React Router 7 | Rutas públicas, privadas y admin |
| Zustand | Sesión y estado global |
| Axios | Cliente HTTP con renovación JWT |
| Firebase 12 | Autenticación y sincronización de salas Karaoke |
| Stripe.js | Checkout y pagos desde el navegador |
| Tailwind CSS + CSS Modules | Estilos globales y componentes |

## Desarrollo

La ejecución principal utiliza el `docker-compose.yml` de la raíz y el `.env` global:

```bash
docker compose up --build frontend backend
```

Para trabajar directamente en el frontend:

```bash
npm install
npm run dev
```

La aplicación queda disponible en `http://localhost:5173` y Vite redirige `/api` hacia Django.

## Scripts

```bash
npm run dev          # servidor de desarrollo
npm run build        # comprobación TypeScript y build Vite
npm run preview      # sirve el build localmente
npm run lint         # ESLint
npm run format       # formatea TypeScript, TSX, CSS y JSON
npm run format:check # comprueba el formato
```

## Configuración

El frontend recibe sus variables mediante el `.env` global de la raíz; Docker Compose las expone al servicio `frontend` durante el desarrollo y el build:

```env
VITE_STRIPE_PUBLIC_KEY=...
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_DATABASE_URL=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
VITE_FIREBASE_VAPID_KEY=...
```

La API usa rutas relativas (`/api`) y no requiere `VITE_API_URL` en la configuración actual.

## Estructura

```text
src/
├── api/          # Cliente Axios, endpoints y módulos por dominio
├── components/   # Componentes reutilizables de canciones, stems, Mix y Karaoke
├── hooks/        # Reproducción, jobs, salas y estado derivado
├── layouts/      # Layout de usuario, autenticación y administración
├── pages/        # auth, cliente, library, create, stems, Karaoke, Mix y admin
├── router/       # rutas privadas, admin y guard Firebase de Karaoke
├── services/     # Firebase Auth, FCM y servicios de aplicación
├── store/        # Zustand y persistencia de sesión
├── types/        # Tipos compartidos de TypeScript
└── index.css     # Tailwind, tokens visuales y estilos base
```

## Convenciones

- Centraliza las rutas en `src/api/endpoints.ts` y las peticiones en `src/api/modules/`.
- Las páginas y componentes no deben llamar directamente a `fetch` o `axios`.
- Usa `useAuthStore` para la sesión y `PrivateRoute` o `AdminRoute` según corresponda.
- Usa Tailwind y los tokens CSS existentes; reserva CSS Modules para estilos específicos del componente.
- Mantén los contratos definidos en [`../gm_backend/docs/01_API_CONTRACT.md`](../gm_backend/docs/01_API_CONTRACT.md).
- Nombra componentes en `PascalCase` y hooks/utilidades en `camelCase`.
