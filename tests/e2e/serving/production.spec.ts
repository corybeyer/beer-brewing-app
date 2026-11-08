import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';

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
  if (expected === 'ready') await expect(page.getByRole('button', { name: 'New recipe', exact: true })).toBeEnabled();
  else await expect(page.getByRole('button', { name: 'New recipe', exact: true })).toBeDisabled();
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

test('manual overview persists through the real API and outage is explicit', async ({ page, request }, testInfo) => {
  await page.goto('/');
  if (expected === 'unavailable') {
    await expect(page.getByRole('button', { name: 'New recipe', exact: true })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Retry loading drafts', exact: true })).toBeVisible();
    await expect(page.getByText('Every good batch starts with a recipe.', { exact: true })).not.toBeVisible();
    const failed = await request.patch('/api/v1/recipe-drafts/missing/overview', { data: { expected_revision: 1, name: 'Must not save', description: null } });
    expect(failed.status()).toBe(503); expect((await failed.json()).error.code).toBe('unavailable');
    return;
  }
  const name = `Runtime draft ${testInfo.project.name} ${randomUUID().slice(0, 8)}`;
  await page.getByRole('button', { name: 'New recipe', exact: true }).click();
  await page.getByRole('textbox', { name: 'Recipe name', exact: true }).fill(name);
  await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Disposable runtime verification only.');
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByText('Draft overview saved.', { exact: true })).toBeVisible();
  await page.reload(); await page.getByRole('button', { name: `Open ${name}`, exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue('Disposable runtime verification only.');
});

test('serves only the public build and preserves HTTP contracts', async ({ request }) => {
  for (const path of ['/component-examples.html', '/src/main.tsx', '/.env', '/.secrets/app-password',
    '/run/secrets/app-password', '/apps/api/brewery_api/api.py', '/api/v1/missing',
    '/assets/%2e%2e%2findex.html']) {
    expect((await request.get(path)).status(), path).toBe(404);
  }
  const index = await request.get('/');
  expect(index.headers()['cache-control']).toBe('no-cache');
  expect(index.headers()['content-security-policy']).toBe("frame-ancestors 'none'");
  expect(index.headers()['x-frame-options']).toBe('DENY');
  expect(index.headers()['content-type']).toContain('text/html');
  expect(await index.text()).not.toContain('/src/main.tsx');
  expect((await request.head('/')).status()).toBe(200);
  expect((await request.get('/health')).status()).toBe(200);
  expect((await request.get('/api/v1/openapi.json')).status()).toBe(200);
});
