import { expect, test } from '@playwright/test';

const readiness = process.env.BREWERY_SERVING_READINESS;
if (readiness !== 'ready' && readiness !== 'unavailable') throw new Error('Set BREWERY_SERVING_READINESS to ready or unavailable');

test('built calculator uses real exact conversions even when database readiness is unavailable', async ({ page, baseURL }) => {
  const origins = new Set<string>();
  const errors: string[] = [];
  page.on('request', (request) => origins.add(new URL(request.url()).origin));
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/#/calculators');
  await expect(page.getByRole('heading', { name: 'Grain & extract conversion', exact: true })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: `Brewing service ${readiness}` })).toBeVisible();
  await page.getByRole('button', { name: 'Load illustrative example' }).click();

  const converted = page.waitForResponse((response) => response.url().endsWith('/api/v1/conversions/fermentable') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  const response = await converted;
  expect(response.status()).toBe(200);
  expect(await response.json()).toMatchObject({
    amount: { numerator: '180', denominator: '37' }, unit: 'lb',
    display_amount: '4.864865', calculation_version: 'gravity-equivalence/v1',
  });
  await expect(page.getByLabel('Target mass', { exact: true })).toHaveText('4.864865 lb');

  await page.getByRole('textbox', { name: 'Target recovery fraction', exact: true }).fill('1.1');
  await expect(page.getByLabel('Target mass', { exact: true })).toHaveCount(0);
  const rejected = page.waitForResponse((value) => value.url().endsWith('/api/v1/conversions/fermentable') && value.request().method() === 'POST');
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  expect((await rejected).status()).toBe(422);
  await expect(page.getByRole('alert')).toContainText('target_yield.recovery_fraction');
  await expect(page.getByRole('textbox', { name: 'Target recovery fraction', exact: true })).toHaveValue('1.1');
  await expect(page.getByRole('textbox', { name: 'Source amount', exact: true })).toHaveValue('3');

  await page.getByRole('textbox', { name: 'Target recovery fraction', exact: true }).fill('0.75');
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByLabel('Target mass', { exact: true })).toHaveText('4.864865 lb');
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect([...origins]).toEqual([new URL(baseURL!).origin]);
  expect(errors).toEqual([]);
});
