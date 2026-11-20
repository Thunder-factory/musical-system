# `gm_frontend` — Arquitectura UI Kit + Feature-Based

Frontend en React 19 + TypeScript + Tailwind CSS 3.4 + Lucide + Zustand (cero librerías de UI externas).

---

## Estructura de `src/`

```text
src/
├── components/
│   ├── ui/                  # Kit Base propio accesible (ÚNICA fuente de controles base)
│   │   ├── button.tsx       # Variantes primary (text-black WCAG AA), secondary, ghost, danger + costCredits
│   │   ├── modal.tsx        # role="dialog", aria-modal, Escape, preventClose, scroll lock, retorno de foco
│   │   ├── confirm-dialog.tsx # Reemplazo único de window.confirm/alert (hook useConfirm)
│   │   ├── select.tsx       # Listbox accesible con teclado
│   │   ├── dropdown-menu.tsx # Menús con cierre exterior y Escape
│   │   ├── input.tsx        # FormField + Input + Textarea con htmlFor y error inline
│   │   ├── empty-state.tsx  # Estado vacío accionable con CTA
│   │   ├── badge.tsx        # Etiquetas de estado y "Próximamente"
│   │   └── toast.tsx        # Toaster con aria-live="polite"
│   ├── layout/              # Shell responsive (app-layout, app-sidebar, app-header, admin-layout, upgrade-modal)
│   └── player/              # Reproductor de audio global persistente
├── features/                # Espejo 1-a-1 de gm_backend/apps/<modulo>/
│   ├── auth/                # Login y registro
│   ├── home/                # Landing pública (/) y lanzador autenticado (/inicio)
│   ├── songs/               # Crear canción (/create), Biblioteca (/library) y puentes entre módulos
│   ├── humming/             # Tarareo + mejora IA
│   ├── stems/               # Separar pistas (desde Biblioteca o archivo local)
│   ├── karaoke/             # Catálogo, generación, reproductor y salas (protegido por flag Firebase)
│   ├── translations/        # Doblaje de videos musicales
│   ├── faceswap/            # Cambiar caras en video
│   ├── mix/                 # Proyectos DJ y editor multipista
│   ├── playlists/           # Playlists, detalle y vista pública (/playlists/public/:token)
│   ├── community/           # Feed público y tendencias
│   ├── recommendations/     # Para ti
│   ├── billing/             # Hub de Pagos/Plan (/payments) y Perfil (/profile)
│   └── admin/               # Dashboard real, gestión de usuarios, roles, planes, reportes y plantillas
├── lib/                     # api-client, endpoints, env (isFirebaseConfigured), cn
├── store/                   # auth.store, active-jobs.store, toast.store
├── hooks/                   # useDismissableLayer
├── router/                  # Definición de rutas con React.lazy y guards
├── services/                # Integración opcional Firebase Auth / Messaging
└── types/                   # Tipos globales compartidos (Karaoke / API)
```

---

## Reglas de UI y UX (Obligatorias)
1. **Usar siempre `src/components/ui/`:** prohibido crear modales ad-hoc, usar `window.alert`/`window.confirm`/`window.prompt`, o crear `<div onClick>` sin botón real.
2. **Legibilidad del código:** mantener archivos `<= 200` líneas (dividir páginas grandes en subcomponentes en `components/` y hooks en `hooks/`).
3. **Contraste y foco:** nunca poner texto blanco sobre `bg-primary` (`#d97745`); usar `Button variant="primary"` (`text-black`). Nunca quitar `outline` sin mantener `:focus-visible`.
4. **Transparencia de créditos:** toda acción paga muestra el costo antes de ejecutarse (`costCredits={N}`), registra trabajos lentos en `useActiveJobsStore` y llama `refreshAuthBalance()` al iniciar/terminar.
5. **Idioma y marca:** español en tuteo neutro (cero voseo) y marca única **`MusicAI`**.
6. **Navegación SPA:** usar siempre `<Link>` o `useNavigate()` de `react-router-dom` (nunca `<a href="/...">` interno que recarga la app y corta el reproductor).
