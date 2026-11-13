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

