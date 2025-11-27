import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

const resolvePath = (relativePath: string) =>
  fileURLToPath(new URL(relativePath, import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolvePath('./src'),
      '@/app': resolvePath('./src/app'),
      '@/layouts': resolvePath('./src/layouts'),
      '@/features': resolvePath('./src/features'),
      '@/shared': resolvePath('./src/shared'),
      '@/assets': resolvePath('./src/assets'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
  },
});
