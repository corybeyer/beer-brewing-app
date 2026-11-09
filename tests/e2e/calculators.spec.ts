import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const endpoint = '**/api/v1/conversions/fermentable';
function result(input: Record<string, unknown>) {
  return { source_mass: input.source_mass, source_yield: input.source_yield, target_yield: input.target_yield,
    amount: { numerator: '180', denominator: '37' }, unit: input.target_unit,
    gravity_points_gallons: { numerator: '135', denominator: '1' }, display_amount: '4.864865',
    display_decimal_places: 6, calculation_version: 'gravity-equivalence/v1' };
}
async function open(page: Page) {
  await page.route('**/api/v1/readiness', (route) => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/api/v1/recipe-drafts?*', (route) => route.fulfill({ json: { items: [], next_offset: null } }));
  await page.goto('/#/calculators');
}

test('calculator starts blank, requires explicit assumptions, and displays the API result accessibly', async ({ page }, testInfo) => {
  let posted: Record<string, unknown> | undefined;
  await page.route(endpoint, (route) => { posted = route.request().postDataJSON(); return route.fulfill({ json: result(posted!) }); });
  await open(page);
  await expect(page.getByLabel('Source amount', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Source potential (PPG)', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Target recovery fraction', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Comparison point for both sides', { exact: true })).toHaveValue('');
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Choose the comparison point');
  expect(posted).toBeUndefined();
  await page.getByRole('button', { name: 'Load illustrative example' }).click();
  await expect(page.getByRole('region', { name: 'Conversion result', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByLabel('Target mass', { exact: true })).toHaveText('4.864865 lb');
  expect(posted).toMatchObject({ source_mass: { amount: '3', unit: 'lb' }, source_yield: { potential_ppg: '45', recovery_fraction: '1', comparison_point: 'kettle' }, target_yield: { potential_ppg: '37', recovery_fraction: '0.75', comparison_point: 'kettle' }, target_unit: 'lb' });
  await expect(page.getByRole('region', { name: 'Conversion result', exact: true })).toContainText('180/37 lb');
  await expect(page.getByText('This does not establish flavor equivalence', { exact: false })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('conversion-calculator.png'), fullPage: true });
});

test('server field validation preserves input and allows a successful retry', async ({ page }) => {
  let valid = false;
  await page.route(endpoint, (route) => route.fulfill(valid ? { json: result(route.request().postDataJSON()) } : {
    status: 422, json: { error: { code: 'invalid_conversion', message: 'Review your assumptions.', issues: [{ path: 'source_yield.recovery_fraction', code: 'invalid_value', message: 'Recovery must be above zero through one.' }] } },
  }));
  await open(page); await page.getByRole('button', { name: 'Load illustrative example' }).click();
  await page.getByLabel('Source recovery fraction', { exact: true }).fill('2');
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Review your assumptions.');
  await expect(page.getByLabel('Source recovery fraction', { exact: true })).toHaveValue('2');
  await expect(page.getByLabel('Source recovery fraction', { exact: true })).toHaveAttribute('aria-invalid', 'true');
  valid = true;
  await page.getByLabel('Source recovery fraction', { exact: true }).fill('1');
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByLabel('Target mass', { exact: true })).toHaveText('4.864865 lb');
});

for (const failure of ['network', 'timeout', 'invalid-response'] as const) {
  test(`calculator preserves assumptions after ${failure} and can retry`, async ({ page }) => {
    let valid = false;
    await page.route(endpoint, (route) => {
      if (valid) return route.fulfill({ json: result(route.request().postDataJSON()) });
      if (failure === 'network') return route.abort('failed');
      if (failure === 'timeout') return Promise.resolve();
      return route.fulfill({ json: { ...result(route.request().postDataJSON()), amount: { numerator: '180', denominator: '0' } } });
    });
    await open(page); await page.getByRole('button', { name: 'Load illustrative example' }).click();
    await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Your entered values are still here', { timeout: 8000 });
    await expect(page.getByLabel('Source amount', { exact: true })).toHaveValue('3');
    await expect(page.getByLabel('Target yield provenance', { exact: true })).toHaveValue(/Illustrative grain benchmark/);
    await expect(page.getByLabel('Target mass', { exact: true })).toHaveCount(0);
    valid = true;
    await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
    await expect(page.getByLabel('Target mass', { exact: true })).toHaveText('4.864865 lb');
  });
}

test('editing or leaving cancels pending calculations so late replies cannot replace a newer result', async ({ page }) => {
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => { release = resolve; });
  let releaseNavigation!: () => void;
  const navigationWaiting = new Promise<void>((resolve) => { releaseNavigation = resolve; });
  let calls = 0;
  await page.route(endpoint, async (route) => {
    calls += 1; if (calls === 1) await waiting; if (calls === 3) await navigationWaiting;
    await route.fulfill({ json: result(route.request().postDataJSON()) }).catch(() => undefined);
  });
  await open(page); await page.getByRole('button', { name: 'Load illustrative example' }).click();
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Calculating…', exact: true })).toBeDisabled();
  await page.getByLabel('Source amount', { exact: true }).fill('4');
  await expect(page.getByRole('button', { name: 'Calculate conversion', exact: true })).toBeEnabled();
  release();
  await expect(page.getByLabel('Target mass', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByLabel('Target mass', { exact: true })).toHaveText('4.864865 lb');
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Calculating…', exact: true })).toBeDisabled();
  await page.getByRole('navigation').getByRole('link', { name: 'Home', exact: true }).click();
  releaseNavigation();
  await expect(page.getByRole('heading', { name: 'More good brewing ahead.' })).toBeVisible();
  await page.getByRole('navigation').getByRole('link', { name: 'Calculators', exact: true }).click();
  await expect(page.getByLabel('Target mass', { exact: true })).toHaveCount(0);
});


test('responses for different assumptions are rejected without clearing the form', async ({ page }) => {
  await page.route(endpoint, (route) => {
    const value = result(route.request().postDataJSON());
    return route.fulfill({ json: { ...value, source_mass: { amount: '999', unit: 'lb' } } });
  });
  await open(page); await page.getByRole('button', { name: 'Load illustrative example' }).click();
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('response could not be read');
  await expect(page.getByLabel('Source amount', { exact: true })).toHaveValue('3');
  await expect(page.getByLabel('Target mass', { exact: true })).toHaveCount(0);
});

test('tiny and long exact results stay readable without browser rounding or overflow', async ({ page }) => {
  let tiny = true;
  await page.route(endpoint, (route) => route.fulfill({ json: { ...result(route.request().postDataJSON()),
    display_amount: tiny ? '<0.000001' : '9999999999999999999999999999999999999999.000000',
    amount: { numerator: tiny ? '1' : '9'.repeat(155), denominator: '1' + '0'.repeat(100) } } }));
  await open(page); await page.getByRole('button', { name: 'Load illustrative example' }).click();
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByLabel('Target mass', { exact: true })).toHaveText('<0.000001 lb');
  tiny = false;
  await page.getByRole('button', { name: 'Calculate conversion', exact: true }).click();
  await expect(page.getByLabel('Target mass', { exact: true })).toContainText('9999999999999999999999999999999999999999.000000');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
