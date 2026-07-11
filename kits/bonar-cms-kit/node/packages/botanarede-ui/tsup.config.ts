import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['esm'],
  dts: true,
  clean: true,
  target: 'es2022',
  splitting: false,
  sourcemap: true,
  external: ['react', 'react-dom', '@botanarede/core', '@botanarede/schema'],
  banner: {
    js: `'use client';`,
  },
});
