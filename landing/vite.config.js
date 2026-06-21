import path from 'path'
import { fileURLToPath } from 'url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { vitePrerenderPlugin } from 'vite-prerender-plugin'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Cible du proxy dev/preview. Défaut: backend local sur :8000.
  // Pour taper la prod en local, définir VITE_DEV_PROXY_TARGET dans .env.local
  // (ex. https://agent-production-c246.up.railway.app) — pas de souci CORS car
  // le navigateur ne parle qu'à localhost, le proxy relaie côté serveur.
  const devApiTarget = (env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000').replace(/\/$/, '')
  const proxy = {
    '/api': { target: devApiTarget, changeOrigin: true },
    '/auth': { target: devApiTarget, changeOrigin: true },
    '/health': { target: devApiTarget, changeOrigin: true },
  }

  return {
    plugins: [
      react(),
      vitePrerenderPlugin({
        renderTarget: '#root',
        prerenderScript: path.resolve(__dirname, 'src/prerender.jsx'),
      }),
    ],
    test: {
      environment: 'node',
      environmentMatchGlobs: [['**/*.dom.test.{js,jsx,mjs}', 'jsdom']],
      include: ['src/**/*.test.{js,mjs,jsx}'],
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined;
            if (id.includes('lucide-react')) return 'vendor-lucide';
            if (id.includes('react-router') || id.includes('react-dom') || id.includes('/react/')) {
              return 'vendor-react';
            }
            return undefined;
          },
        },
      },
    },
    server: {
      port: 5173,
      proxy,
    },
    preview: {
      port: 3000,
      proxy,
    },
  }
})
