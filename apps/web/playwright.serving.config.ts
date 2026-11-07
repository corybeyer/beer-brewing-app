import { defineConfig } from '@playwright/test';
import foundation from './playwright.config';

if (!process.env.BREWERY_SERVING_BASE_URL) throw new Error('Set BREWERY_SERVING_BASE_URL to the isolated candidate server');

export default defineConfig({
  ...foundation,
  testDir: '../../tests/e2e/serving',
  testIgnore: [],
  outputDir: `../../tests/e2e/test-results/serving-${process.env.BREWERY_SERVING_PHASE ?? 'local'}`,
  webServer: undefined,
  use: { ...foundation.use, baseURL: process.env.BREWERY_SERVING_BASE_URL },
});
