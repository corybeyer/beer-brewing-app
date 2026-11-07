import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';

const workspaceRoot = resolve(import.meta.dirname, '../..');

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    fs: {
      allow: ['apps/web', 'packages/ui', 'packages/design-system', 'packages/communications', 'node_modules']
        .map((directory) => resolve(workspaceRoot, directory)),
      deny: ['**/.secrets/**', '**/.env', '**/.env.*', '**/.git/**', '**/*.{crt,pem,key}'],
    },
    proxy: { '/api': { target: 'http://127.0.0.1:8081', timeout: 7000 } },
  },
});
