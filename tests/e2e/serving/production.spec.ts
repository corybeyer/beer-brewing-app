import { expect, test } from '@playwright/test';

const expected = process.env.BREWERY_SERVING_READINESS;
if (expected !== 'ready' && expected !== 'unavailable') throw new Error('Set BREWERY_SERVING_READINESS to ready or unavailable');

test('built UI uses the real API on the same origin', async ({ page, request, baseURL }, testInfo) => {
  const origins = new Set<string>();
  const errors: string[] = [];
  page.on('request', (request) => origins.add(new URL(request.url()).origin));
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Recipe library', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toContainText(`Brewing service ${expected}`);
  await expect(page.getByRole('button', { name: 'New recipe' })).toBeDisabled();
  await page.getByRole('button', { name: 'Check connection again' }).click();
  await expect(page.getByRole('status')).toContainText(`Brewing service ${expected}`);
  const response = await request.get('/api/v1/readiness');
  expect(response.status()).toBe(expected === 'ready' ? 200 : 503);
  expect(await response.json()).toEqual({ status: expected });
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  expect([...origins]).toEqual([new URL(baseURL!).origin]);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('served-ui.png'), fullPage: true });
});

test('serves only the public build and preserves HTTP contracts', async ({ request }) => {
  for (const path of ['/component-examples.html', '/src/main.tsx', '/.env', '/.secrets/app-password',
    '/run/secrets/app-password', '/apps/api/brewery_api/api.py', '/api/v1/missing',
    '/assets/%2e%2e%2findex.html']) {
    expect((await request.get(path)).status(), path).toBe(404);
  }
  const index = await request.get('/');
  expect(index.headers()['cache-control']).toBe('no-cache');
  expect(index.headers()['content-type']).toContain('text/html');
  expect(await index.text()).not.toContain('/src/main.tsx');
  expect((await request.head('/')).status()).toBe(200);
  expect((await request.get('/health')).status()).toBe(200);
  expect((await request.get('/api/v1/openapi.json')).status()).toBe(200);
});
