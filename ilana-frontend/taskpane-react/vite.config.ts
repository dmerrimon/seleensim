import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './', // Relative paths for Office add-in
  build: {
    outDir: 'dist',
    // Generate a single HTML file that can replace taskpane.html
    rollupOptions: {
      output: {
        // Keep asset names predictable
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
  server: {
    port: 3000,
  },
})
