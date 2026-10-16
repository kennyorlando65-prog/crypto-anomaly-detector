import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    // Pin the worker pool. Vitest defaults to one worker per CPU, which on a
    // high-core machine with a small memory cgroup gets the run OOM-killed
    // before it can report. Two workers is plenty for a suite this size and
    // makes the result the same on a laptop, a CI runner and a container.
    maxWorkers: 2,
    minWorkers: 1,
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
});
