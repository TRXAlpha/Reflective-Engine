import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// dev proxy => forward /api/* to your Flask backend on 8181
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,

    // bind to all addresses so ngrok can connect
    host: '0.0.0.0',

    // public origin that will be used for links / HMR client
    origin: 'https://ghost.solnetmesh.top/',

    // HMR must use the ngrok host and secure websockets (wss) when using ngrok HTTPS
    hmr: {
      protocol: 'wss',
      host: 'paleomagnetic-kasi-deuteranomalous.ngrok-free.dev',
      port: 443,
    },

    proxy: {
      '/api': {
        target: 'http://localhost:8181',
        changeOrigin: true,
        secure: false,
        ws: true,
      },
    },

    // optional: allow files outside project root if you hit an fs restriction
    // fs: { allow: ['..'] },
  },
})
