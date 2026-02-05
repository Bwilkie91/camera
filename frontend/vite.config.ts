import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-query': ['@tanstack/react-query', 'zustand'],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
  server: {
    proxy: {
      '/api': { target: 'http://localhost:5000', changeOrigin: true },
      '/streams': { target: 'http://localhost:5000', changeOrigin: true },
      '/sites': { target: 'http://localhost:5000', changeOrigin: true },
      '/camera_positions': { target: 'http://localhost:5000', changeOrigin: true },
      '/get_data': { target: 'http://localhost:5000', changeOrigin: true },
      '/events': { target: 'http://localhost:5000', changeOrigin: true },
      '/video_feed': { target: 'http://localhost:5000', changeOrigin: true },
      '/thermal_feed': { target: 'http://localhost:5000', changeOrigin: true },
      '/export_data': { target: 'http://localhost:5000', changeOrigin: true },
      '/health': { target: 'http://localhost:5000', changeOrigin: true },
      '/recording': { target: 'http://localhost:5000', changeOrigin: true },
      '/recordings': { target: 'http://localhost:5000', changeOrigin: true },
      '/toggle_recording': { target: 'http://localhost:5000', changeOrigin: true },
      '/move_camera': { target: 'http://localhost:5000', changeOrigin: true },
      '/me': { target: 'http://localhost:5000', changeOrigin: true },
      '/login': { target: 'http://localhost:5000', changeOrigin: true },
      '/logout': { target: 'http://localhost:5000', changeOrigin: true },
      '/mfa': { target: 'http://localhost:5000', changeOrigin: true },
      '/change_password': { target: 'http://localhost:5000', changeOrigin: true },
      '/config': { target: 'http://localhost:5000', changeOrigin: true },
      '/audit_log': { target: 'http://localhost:5000', changeOrigin: true },
      '/ws': { target: 'http://localhost:5000', ws: true },
    },
  },
})
