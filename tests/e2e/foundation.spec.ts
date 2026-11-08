import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { resolve } from 'node:path';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';

const endpoint = '**/api/v1/readiness';
const ready = { status: 200, contentType: 'application/json', body: '{"status":"ready"}' };

test('development server refuses secret and backend source files', async ({ request }) => {
  const root = resolve(import.meta.dirname, '../..');
  mkdirSync(resolve(root, '.secrets'), { recursive: true, mode: 0o700 });
  const fixture = mkdtempSync(resolve(root, '.secrets/vite-boundary-'));
  try {
    // Synthetic test data only; never read or overwrite actual credentials.
    writeFileSync(resolve(fixture, 'fixture'), 'test-only-private-fixture', { mode: 0o600 });
    for (const privatePath of [resolve(fixture, 'fixture'), resolve(root, '.env.example'), resolve(root, 'apps/api/brewery_api/api.py')]) {
      const response = await request.get(`/@fs${privatePath}`);
      expect([403, 404]).toContain(response.status());
    }
  } finally {
    rmSync(fixture, { recursive: true });
  }
});

async function mockReady(page: Page) {
  await page.route(endpoint, (route) => route.fulfill(ready));
  await page.route('**/api/v1/recipe-drafts?*', (route) => route.fulfill({ status: 200, json: { items: [], next_offset: null } }));
}

test('recipe library is honest, responsive, and accessible', async ({ page }, testInfo) => {
  await mockReady(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Recipe library', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Brewing service ready');
  await expect(page.getByRole('button', { name: 'New recipe', exact: true })).toBeEnabled();
  await expect(page.getByRole('searchbox', { name: 'Search recipes' })).toBeDisabled();
  await expect(page.getByRole('combobox', { name: 'Filter by style' })).toBeDisabled();
  await expect(page.getByText('Create a draft and start with a name and your notes.', { exact: false })).toBeVisible();
  await expect(page.getByRole('navigation').getByRole('link', { name: 'Recipes' })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('navigation').getByText('Brew day')).toHaveAttribute('aria-disabled', 'true');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('recipe-library.png'), fullPage: true });
});

test('checks on load and permits an accessible retry after unavailable response', async ({ page }) => {
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => { release = resolve; });
  let available = false;
  await page.route(endpoint, async (route) => {
    await waiting;
    await route.fulfill(available ? ready : { status: 503, contentType: 'application/json', body: '{"status":"unavailable"}' });
  });
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Checking connection' })).toBeDisabled();
  await expect(page.getByRole('region', { name: 'Brewing service connection' })).toHaveAttribute('aria-busy', 'true');
  release();
  await expect(page.getByRole('status')).toContainText('Brewing service unavailable');
  available = true;
  await page.getByRole('button', { name: 'Check connection again' }).click();
  await expect(page.getByRole('status')).toContainText('Brewing service ready');
  // Readiness alone does not establish that the draft collection can be loaded.
  await expect(page.getByRole('button', { name: 'New recipe' })).toBeDisabled();
});

for (const failure of ['invalid-status', 'invalid-json', 'network', 'timeout'] as const) {
  test(`treats ${failure} as unavailable`, async ({ page }) => {
    await page.route(endpoint, (route) => {
      if (failure === 'network') return route.abort('failed');
      if (failure === 'timeout') return Promise.resolve();
      return route.fulfill({ status: 200, contentType: 'application/json', body: failure === 'invalid-json' ? '<html>error</html>' : '{"status":"something-else"}' });
    });
    await page.goto('/');
    await expect(page.getByRole('status')).toContainText('Brewing service unavailable', { timeout: 8000 });
    await expect(page.getByRole('button', { name: 'Check connection again' })).toBeEnabled();
  });
}

test('navigation survives refresh, browser history, and unknown routes', async ({ page }) => {
  await mockReady(page);
  await page.goto('/');
  await page.getByRole('navigation').getByRole('link', { name: 'Settings' }).click();
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeFocused();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  await page.getByRole('navigation').getByRole('link', { name: 'Home', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'More good brewing ahead.' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  await page.goForward();
  await expect(page).toHaveTitle('Home · Homebrew');
  await page.goto('/#/missing');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  await page.getByRole('link', { name: 'Back to recipes' }).click();
  await expect(page.getByRole('heading', { name: 'Recipe library', exact: true })).toBeFocused();
});

test('keyboard skip link and connection button have visible focus and touch size', async ({ page }) => {
  await mockReady(page);
  await page.goto('/');
  await expect(page.getByRole('status')).toContainText('Brewing service ready');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
  await page.keyboard.press('Tab');
  const retry = page.getByRole('button', { name: 'Check connection again' });
  await expect(retry).toBeFocused();
  expect(await retry.evaluate((element) => getComputedStyle(element).boxShadow)).not.toBe('none');
  const box = await retry.boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(48);
  await page.keyboard.press('Enter');
  await expect(page.getByRole('status')).toContainText('Brewing service ready');
});

test('recovers on reconnect without a stale request overwriting the result', async ({ page }) => {
  let slow = false;
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => { release = resolve; });
  let delivered!: () => void;
  const oldRequestFinished = new Promise<void>((resolve) => { delivered = resolve; });
  await page.route(endpoint, async (route) => {
    if (slow) { await waiting; await route.fulfill({ ...ready, status: 503, body: '{"status":"unavailable"}' }); delivered(); }
    else await route.fulfill(ready);
  });
  await page.goto('/');
  await expect(page.getByRole('status')).toContainText('Brewing service ready');
  slow = true;
  await page.getByRole('button', { name: 'Check connection again' }).click();
  await expect(page.getByRole('button', { name: 'Checking connection' })).toBeDisabled();
  slow = false;
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect(page.getByRole('status')).toContainText('Brewing service ready');
  release();
  await oldRequestFinished;
  await expect(page.getByRole('status')).toContainText('Brewing service ready');
});

test('shared component examples cover enabled, disabled, busy, and invalid states', async ({ page }, testInfo) => {
  await page.goto('/component-examples.html');
  const primary = page.getByRole('button', { name: 'Try primary button' });
  await primary.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByLabel('Example count')).toHaveText('1');
  await expect(page.getByRole('button', { name: 'Disabled example' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Saving…' })).toHaveAttribute('aria-busy', 'true');
  await page.getByRole('searchbox', { name: 'Find an ingredient' }).fill('Cascade');
  await expect(page.getByLabel('Search value')).toHaveText('Cascade');
  await page.getByRole('combobox', { name: 'Beer style' }).selectOption('Custom');
  await expect(page.getByLabel('Selected style')).toHaveText('Custom');
  await expect(page.getByRole('searchbox', { name: 'Search with error' })).toHaveAccessibleDescription('Enter an ingredient name.');
  await page.getByRole('textbox', { name: 'Example recipe name', exact: true }).fill('Pale ale');
  await page.getByRole('textbox', { name: 'Example description', exact: true }).fill('Notes');
  const description = page.getByRole('textbox', { name: 'Example description', exact: true });
  await description.focus();
  expect(await description.evaluate((element) => getComputedStyle(element).boxShadow)).not.toBe('none');
  expect((await description.boundingBox())?.height).toBeGreaterThanOrEqual(48);
  await expect(page.getByRole('textbox', { name: 'Name with error', exact: true })).toHaveAccessibleDescription('Review this name.');
  await expect(page.getByRole('textbox', { name: 'Description with error', exact: true })).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByRole('textbox', { name: 'Disabled description', exact: true })).toBeDisabled();
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('design-system.png'), fullPage: true });
});

test('other views retain accessible structure', async ({ page }) => {
  await mockReady(page);
  for (const route of ['home', 'settings', 'missing']) {
    await page.goto(`/#/${route}`);
    await expect(page.getByRole('status')).toContainText('Brewing service ready');
    expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
  }
});
