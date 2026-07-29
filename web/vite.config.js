import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Kantorei — Notenarchiv',
        short_name: 'Kantorei',
        description: 'Selbstgehostetes Notenarchiv für Kirchenmusik',
        lang: 'de',
        theme_color: '#2E6EB5',
        background_color: '#16181D',
        display: 'standalone',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        // Verovio-WASM-Chunk (~8 MB) NICHT vorab cachen — lädt bei Bedarf.
        // Eigener geteilter Chunk (NotenView + VerovioPreview) heißt verovio-*.js.
        globIgnores: ['**/verovio-*.js', '**/NotenView-*.js'],
        navigateFallbackDenylist: [/^\/api/],
        runtimeCaching: [
          {
            // Scan-PDFs: offline-fest (einmal geladen -> im Gottesdienst immer verfügbar)
            urlPattern: /\/api\/dateien\/[^/]+\/download$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'noten-scans',
              expiration: { maxEntries: 500, maxAgeSeconds: 60 * 60 * 24 * 180 },
              cacheableResponse: { statuses: [0, 200] }
            }
          },
          {
            urlPattern: /\/api\/dateien\/[^/]+\/thumbnail$/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'noten-thumbs',
              expiration: { maxEntries: 1000, maxAgeSeconds: 60 * 60 * 24 * 60 }
            }
          }
        ]
      }
    })
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@brand': fileURLToPath(new URL('../brand', import.meta.url))
    }
  },
  server: {
    fs: { allow: ['..'] },
    proxy: { '/api': 'http://127.0.0.1:8001' }
  }
})
