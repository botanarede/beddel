import { defineConfig } from 'tsup'

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    'react/index': 'src/react/index.ts',
    'server/index': 'src/server/index.ts',
    'providers/firebase/index': 'src/providers/firebase/index.ts',
  },
  format: ['esm'],
  dts: true,
  clean: true,
  sourcemap: true,
  target: 'es2022',
  platform: 'neutral',
  external: [
    'react',
    'react-dom',
    'firebase',
    'firebase/app',
    'firebase/auth',
    'firebase/app-check',
    'firebase/firestore',
    'firebase/storage',
    'firebase-admin',
    'firebase-admin/app',
    'firebase-admin/app-check',
    'firebase-admin/auth',
    'firebase-admin/firestore',
    'next/server',
  ],
  splitting: false,
  treeshake: true,
})
