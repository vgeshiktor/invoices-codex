import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    clearMocks: true,
    css: true,
    environment: 'jsdom',
    restoreMocks: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});
