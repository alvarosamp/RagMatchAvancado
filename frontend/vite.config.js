import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    {
      name: 'serve-embedded-crm',
      configureServer(server) {
        const crmIndexPath = resolve(process.cwd(), 'public/crm/index.html')

        server.middlewares.use((req, res, next) => {
          const url = req.url?.split('?')[0] || ''
          const isCrmAppRoute = url === '/crm' || url === '/crm/' || (
            url.startsWith('/crm/') &&
            !url.startsWith('/crm/assets/') &&
            !url.includes('.')
          )

          if (!isCrmAppRoute) {
            next()
            return
          }

          try {
            const html = readFileSync(crmIndexPath, 'utf8')
            res.statusCode = 200
            res.setHeader('Content-Type', 'text/html; charset=utf-8')
            res.end(html)
          } catch {
            next()
          }
        })
      },
    },
    react(),
  ],
  server: {
    port: Number(process.env.PORT) || 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
