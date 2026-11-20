// import { defineConfig } from 'vite'
// import react from '@vitejs/plugin-react'
// import path from 'path'

// export default defineConfig({
//   plugins: [react()],
//   resolve: {
//     alias: {
//       '@': path.resolve(__dirname, './src'),
//     },
//   },
// })


import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],

    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },

    server: {
      host: '0.0.0.0',
      port: Number(env.FRONTEND_INTERNAL_PORT || 5173),
      strictPort: true,
      // Dominios extra aceptados por el servidor de Vite (p. ej. el dominio público en Azure
      // detrás de Caddy). Lista separada por comas en FRONTEND_ALLOWED_HOSTS; vacío = solo local.
      allowedHosts: (env.FRONTEND_ALLOWED_HOSTS || '')
        .split(',')
        .map((host) => host.trim())
        .filter(Boolean),

      proxy: {
        '/api': {
          target: `http://backend:${env.BACKEND_INTERNAL_PORT || 8000}`,
          changeOrigin: true,
        },
      },

      watch: {
        usePolling: env.CHOKIDAR_USEPOLLING === 'true',
      },
    },
  }
})

