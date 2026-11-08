import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { RecipeOverview, RecipeIngredient } from '@brewery/communications/recipes';

const endpoint = '**/api/v1/recipe-drafts**';
const failure = (code: string, message: string, issues: { path: string; code: string; message: string }[] = []) => ({ error: { code, message, issues } });

async function server(page: Page, loseFirstCreate = false) {
  const drafts = new Map<string, RecipeOverview>();
  const ingredients = new Map<string, RecipeIngredient[]>();
  const keys: string[] = []; const revisions: number[] = [];
  await page.route('**/api/v1/readiness', (route) => route.fulfill({ json: { status: 'ready' } }));
  await page.route(endpoint, async (route) => {
    const request = route.request(); const url = new URL(request.url());
    if (request.method() === 'POST') {
      const key = request.postDataJSON().creation_id as string; keys.push(key);
      const previous = [...drafts.values()].find((draft) => draft.recipe_id === key);
      const draft: RecipeOverview = previous ?? { recipe_id: key, version_id: `draft-${key}`, version_number: 1,
        name: null, description: null, edit_revision: 1, status: 'draft' };
      drafts.set(draft.version_id, draft);
      if (loseFirstCreate && keys.length === 1) return route.abort('failed');
      return route.fulfill({ status: previous ? 200 : 201, json: draft });
    }
    if (request.method() === 'PATCH') {
      const id = decodeURIComponent(url.pathname.split('/').at(-2)!); const draft = drafts.get(id)!;
      const body = request.postDataJSON(); revisions.push(body.expected_revision);
      if (body.expected_revision !== draft.edit_revision) return route.fulfill({ status: 409, json: failure('conflict', 'This draft changed elsewhere. Review the latest saved version before retrying.') });
      if (url.pathname.endsWith('/ingredients')) {
        ingredients.set(id, body.ingredients);
        drafts.set(id, { ...draft, edit_revision: draft.edit_revision + 1 });
        return route.fulfill({ json: { version_id: id, edit_revision: draft.edit_revision + 1, ingredients: body.ingredients } });
      }
      const saved = { ...draft, name: body.name, description: body.description, edit_revision: draft.edit_revision + 1 };
      drafts.set(id, saved); return route.fulfill({ json: saved });
    }
    if (url.pathname === '/api/v1/recipe-drafts') return route.fulfill({ json: { items: [...drafts.values()].reverse(), next_offset: null } });
    if (url.pathname.endsWith('/ingredients')) {
      const id = decodeURIComponent(url.pathname.split('/').at(-2)!);
      const draft = drafts.get(id)!;
      return route.fulfill({ json: { version_id: id, edit_revision: draft.edit_revision, ingredients: ingredients.get(id) ?? [] } });
    }
    const draft = drafts.get(decodeURIComponent(url.pathname.split('/').at(-1)!));
    return route.fulfill({ status: draft ? 200 : 404, json: draft ?? failure('not_found', 'This draft could not be found.') });
  });
  return { drafts, ingredients, keys, revisions };
}

async function newDraft(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'New recipe', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Recipe name', exact: true })).toBeFocused();
}

test('create, save, reload, and reopen a recipe overview accessibly', async ({ page }, testInfo) => {
  await server(page); await newDraft(page);
  await page.getByRole('textbox', { name: 'Recipe name', exact: true }).fill('Garage pale ale');
  await page.getByRole('textbox', { name: 'Description', exact: true }).fill('A small experiment for the next brew.');
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByText('Draft overview saved.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save overview', exact: true })).toBeDisabled();
  await page.reload();
  await page.getByRole('button', { name: 'Open Garage pale ale', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue('A small experiment for the next brew.');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('recipe-editor.png'), fullPage: true });
});

test('lost creation response survives refresh and reuses a UUID without randomUUID', async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(crypto, 'randomUUID', { value: undefined }));
  const api = await server(page, true);
  await page.goto('/'); await page.getByRole('button', { name: 'New recipe', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('could not be completed');
  await page.reload();
  await page.getByRole('button', { name: 'Retry new draft', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Recipe name', exact: true })).toBeVisible();
  expect(api.keys).toHaveLength(2); expect(api.keys[1]).toBe(api.keys[0]); expect(api.drafts.size).toBe(1);
  expect(api.keys[0]).toMatch(/^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/);
});

test('retrying a created draft resets pagination without skipping an existing draft', async ({ page }) => {
  const api = await server(page, true);
  await page.route('**/api/v1/recipe-drafts?*', (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get('offset'));
    const all = [...api.drafts.values()].reverse();
    return route.fulfill({ json: { items: all.slice(offset, offset + 50), next_offset: offset + 50 < all.length ? offset + 50 : null } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'New recipe', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('could not be completed');
  for (let index = 0; index < 51; index += 1) {
    api.drafts.set(`existing-${index}`, { recipe_id: `recipe-${index}`, version_id: `existing-${index}`,
      version_number: 1, name: `Existing draft ${index}`, description: null, edit_revision: 1, status: 'draft' });
  }
  await page.reload();
  await page.getByRole('button', { name: 'Retry new draft', exact: true }).click();
  await expect(page.getByText('New draft created. Add a name and description when you are ready.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Load more drafts', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Load more drafts', exact: true })).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Open Existing draft 0', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Saved recipe drafts', exact: true }).getByRole('heading', { level: 2 })).toHaveCount(52);
  expect(api.keys[1]).toBe(api.keys[0]); expect(api.drafts.size).toBe(52);
});

test('failed saves and field validation retain entered values until a successful retry', async ({ page }) => {
  await server(page); await newDraft(page);
  let attempt = 0;
  await page.route('**/overview', (route) => {
    attempt += 1;
    if (attempt === 1) return route.fulfill({ status: 503, json: failure('unavailable', 'Recipe storage is unavailable.') });
    if (attempt === 2) return route.fulfill({ status: 422, json: failure('validation_error', 'Check the highlighted fields.', [{ path: 'name', code: 'invalid_name', message: 'Review the recipe name.' }]) });
    return route.fallback();
  });
  const name = page.getByRole('textbox', { name: 'Recipe name', exact: true });
  await name.fill('Keep this name');
  await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Keep these notes');
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('unavailable'); await expect(name).toHaveValue('Keep this name');
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(name).toHaveAttribute('aria-invalid', 'true'); await expect(name).toHaveAccessibleDescription(/Review the recipe name/);
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue('Keep these notes');
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByText('Draft overview saved.', { exact: true })).toBeVisible();
});

test('conflict review retains my text and requires an explicit retry at the latest revision', async ({ page }) => {
  const api = await server(page); await newDraft(page);
  await page.getByRole('textbox', { name: 'Recipe name', exact: true }).fill('My changes');
  const draft = [...api.drafts.values()][0]; api.drafts.set(draft.version_id, { ...draft, name: 'Other device', edit_revision: 2 });
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Save overview', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Review latest saved version', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Latest saved overview' })).toContainText('Other device');
  await expect(page.getByRole('textbox', { name: 'Recipe name', exact: true })).toHaveValue('My changes');
  await page.getByRole('button', { name: 'Keep my values', exact: true }).click();
  expect(api.revisions).toEqual([1]);
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByText('Draft overview saved.', { exact: true })).toBeVisible();
  expect(api.revisions).toEqual([1, 2]); expect(api.drafts.get(draft.version_id)?.name).toBe('My changes');
});

test('unsaved text survives app navigation and switching drafts requires a choice', async ({ page }) => {
  const api = await server(page); await newDraft(page);
  await page.getByRole('textbox', { name: 'Recipe name', exact: true }).fill('Unsaved idea');
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await page.getByRole('link', { name: 'Recipes', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Recipe name', exact: true })).toHaveValue('Unsaved idea');
  await page.getByRole('button', { name: 'New recipe', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Keep editing', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Recipe name', exact: true })).toHaveValue('Unsaved idea');
  await page.getByRole('button', { name: 'New recipe', exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes and continue', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Recipe name', exact: true })).toHaveValue(''); expect(api.drafts.size).toBe(2);
});

test('loading and invalid responses never present an empty database as fact', async ({ page }) => {
  await server(page);
  let release!: () => void; const waiting = new Promise<void>((resolve) => { release = resolve; });
  let malformed = true;
  await page.route('**/api/v1/recipe-drafts?*', async (route) => {
    await waiting;
    if (malformed) return route.fulfill({ json: { items: [{ name: 'Bad payload' }], next_offset: null } });
    return route.fallback();
  });
  await page.goto('/');
  await expect(page.getByText('Loading recipe drafts…', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'New recipe', exact: true })).toBeDisabled(); release();
  await expect(page.getByRole('alert')).toContainText('unreadable');
  await expect(page.getByText('Every good batch starts with a recipe.', { exact: true })).not.toBeVisible();
  malformed = false; await page.getByRole('button', { name: 'Retry loading drafts', exact: true }).click();
  await expect(page.getByRole('button', { name: 'New recipe', exact: true })).toBeEnabled();
});

test('a late list refresh cannot overwrite the name from a completed save', async ({ page }) => {
  const api = await server(page); await newDraft(page);
  const old = [...api.drafts.values()];
  let release!: () => void; const waiting = new Promise<void>((resolve) => { release = resolve; });
  let delivered!: () => void; const finished = new Promise<void>((resolve) => { delivered = resolve; });
  await page.route('**/api/v1/recipe-drafts?*', async (route) => { await waiting; await route.fulfill({ json: { items: old, next_offset: null } }); delivered(); });
  await page.getByRole('button', { name: 'Refresh drafts', exact: true }).click();
  await page.getByRole('textbox', { name: 'Recipe name', exact: true }).fill('Latest saved name');
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByText('Draft overview saved.', { exact: true })).toBeVisible(); release();
  await finished;
  await expect(page.getByRole('heading', { name: 'Latest saved name', exact: true })).toBeVisible();
});

test('a timed-out save that committed requires review instead of a duplicate write', async ({ page }) => {
  const api = await server(page); await newDraft(page);
  const draft = [...api.drafts.values()][0];
  let release!: () => void; const waiting = new Promise<void>((resolve) => { release = resolve; });
  let delivered!: () => void; const finished = new Promise<void>((resolve) => { delivered = resolve; });
  let first = true;
  await page.route('**/overview', async (route) => {
    if (!first) return route.fallback();
    first = false;
    const body = route.request().postDataJSON();
    const saved = { ...draft, name: body.name, description: body.description, edit_revision: 2 };
    api.drafts.set(saved.version_id, saved);
    await waiting; await route.fulfill({ json: saved }); delivered();
  });
  await page.getByRole('textbox', { name: 'Recipe name', exact: true }).fill('Committed while waiting');
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('could not be completed', { timeout: 8000 });
  await expect(page.getByRole('textbox', { name: 'Recipe name', exact: true })).toHaveValue('Committed while waiting');
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'This draft changed elsewhere', exact: true })).toBeVisible();
  release(); await finished;
  await page.getByRole('button', { name: 'Review latest saved version', exact: true }).click();
  await page.getByRole('button', { name: 'Use saved values', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Save overview', exact: true })).toBeDisabled();
  expect(api.drafts.get(draft.version_id)?.edit_revision).toBe(2);
});

test('ingredient quantities persist exactly and unsaved rows survive navigation', async ({ page }, testInfo) => {
  const api = await server(page); await newDraft(page);
  await page.getByRole('button', { name: 'Add ingredient', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Ingredient 1 name', exact: true })).toBeFocused();
  await page.getByRole('textbox', { name: 'Ingredient 1 name', exact: true }).fill('Cascade');
  await page.getByRole('combobox', { name: 'Ingredient 1 category', exact: true }).selectOption('hops');
  await page.getByRole('textbox', { name: 'Ingredient 1 quantity', exact: true }).fill('20.123456789012');
  await page.getByRole('combobox', { name: 'Ingredient 1 unit', exact: true }).selectOption('g');
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await page.getByRole('link', { name: 'Recipes', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Ingredient 1 quantity', exact: true })).toHaveValue('20.123456789012');
  await page.getByRole('button', { name: 'New recipe', exact: true }).click();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await page.getByRole('button', { name: 'Save ingredients', exact: true }).click();
  await expect(page.getByText('Ingredients saved.', { exact: true })).toBeVisible();
  await page.getByRole('textbox', { name: 'Recipe name', exact: true }).fill('Hops experiment');
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByText('Draft overview saved.', { exact: true })).toBeVisible();
  await page.reload(); await page.getByRole('button', { name: 'Open Hops experiment', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Ingredient 1 quantity', exact: true })).toHaveValue('20.123456789012');
  expect([...api.ingredients.values()][0][0].quantity).toBe('20.123456789012');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
  const rowBounds = await page.getByRole('region', { name: 'Ingredient 1', exact: true }).boundingBox();
  const inputBounds = await page.getByRole('textbox', { name: 'Ingredient 1 name', exact: true }).boundingBox();
  expect(inputBounds!.x + inputBounds!.width).toBeLessThanOrEqual(rowBounds!.x + rowBounds!.width);
  await page.screenshot({ path: testInfo.outputPath('ingredient-editor.png'), fullPage: true });
  await page.getByRole('button', { name: 'Remove ingredient 1', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Add ingredient', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Save ingredients', exact: true }).click();
  await expect(page.getByText('Ingredients saved.', { exact: true })).toBeVisible();
  expect([...api.ingredients.values()][0]).toEqual([]);
});

test('ingredient validation and conflicts preserve rows and require explicit review', async ({ page }) => {
  const api = await server(page); await newDraft(page);
  await page.getByRole('button', { name: 'Add ingredient', exact: true }).click();
  await page.getByRole('textbox', { name: 'Ingredient 1 name', exact: true }).fill('Keep this grain');
  await page.getByRole('textbox', { name: 'Ingredient 1 quantity', exact: true }).fill('0');
  let invalid = true;
  await page.route('**/ingredients', (route) => {
    if (route.request().method() === 'PATCH' && invalid) return route.fulfill({ status: 422, json: failure('validation_error', 'Check the highlighted fields.', [
      { path: 'ingredients[0].quantity', code: 'invalid_quantity', message: 'Supply a finite positive decimal quantity.' }]) });
    return route.fallback();
  });
  await page.getByRole('button', { name: 'Save ingredients', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Ingredient 1 quantity', exact: true })).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByRole('textbox', { name: 'Ingredient 1 name', exact: true })).toHaveValue('Keep this grain');
  invalid = false;
  await page.getByRole('textbox', { name: 'Ingredient 1 quantity', exact: true }).fill('4.5');
  const draft = [...api.drafts.values()][0];
  api.drafts.set(draft.version_id, { ...draft, name: 'Other device name', edit_revision: 2 });
  await page.getByRole('button', { name: 'Save ingredients', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Save ingredients', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Review saved ingredients', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Latest saved ingredients', exact: true })).toContainText('No ingredients saved.');
  await page.getByRole('button', { name: 'Keep my ingredient changes', exact: true }).click();
  await page.getByRole('button', { name: 'Save ingredients', exact: true }).click();
  await expect(page.getByText('Ingredients saved.', { exact: true })).toBeVisible();
  // A newer ingredient revision must not silently authorize overwriting stale overview text.
  await page.getByRole('textbox', { name: 'Recipe name', exact: true }).fill('Stale overview');
  await page.getByRole('button', { name: 'Save overview', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'This draft changed elsewhere', exact: true })).toBeVisible();
  expect(api.drafts.get(draft.version_id)?.name).toBe('Other device name');
});

test('failed ingredient loads stay distinct from an empty list and can be retried', async ({ page }) => {
  await server(page);
  let unavailable = true;
  await page.route('**/ingredients', (route) => unavailable
    ? route.fulfill({ status: 503, json: failure('unavailable', 'Recipe storage is unavailable.') }) : route.fallback());
  await newDraft(page);
  await expect(page.getByRole('button', { name: 'Add ingredient', exact: true })).toBeDisabled();
  await expect(page.getByText('No ingredients in this draft yet.', { exact: true })).not.toBeVisible();
  unavailable = false;
  await page.getByRole('button', { name: 'Retry loading ingredients', exact: true }).click();
  await page.getByRole('button', { name: 'Add ingredient', exact: true }).click();
  await page.getByRole('textbox', { name: 'Ingredient 1 name', exact: true }).fill('Discard this row');
  await page.getByRole('button', { name: 'Discard ingredient changes', exact: true }).click();
  await expect(page.getByText('No ingredients in this draft yet.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Add ingredient', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Add ingredient', exact: true }).click();
  await page.getByRole('textbox', { name: 'Ingredient 1 name', exact: true }).fill('Unsaved row');
  await page.getByRole('button', { name: 'New recipe', exact: true }).click();
  await page.getByRole('button', { name: 'Discard changes and continue', exact: true }).click();
  await expect(page.getByText('No ingredients in this draft yet.', { exact: true })).toBeVisible();
});

test('failed and timed-out ingredient saves retain rows and reconcile a committed write', async ({ page }) => {
  const api = await server(page); await newDraft(page);
  await page.getByRole('button', { name: 'Add ingredient', exact: true }).click();
  await page.getByRole('textbox', { name: 'Ingredient 1 name', exact: true }).fill('Keep after failures');
  let attempt = 0;
  let release!: () => void; const waiting = new Promise<void>((resolve) => { release = resolve; });
  let delivered!: () => void; const finished = new Promise<void>((resolve) => { delivered = resolve; });
  await page.route('**/ingredients', async (route) => {
    if (route.request().method() !== 'PATCH') return route.fallback();
    attempt += 1;
    if (attempt === 1) return route.fulfill({ status: 503, json: failure('unavailable', 'Recipe storage is unavailable.') });
    if (attempt !== 2) return route.fallback();
    const draft = [...api.drafts.values()][0];
    const rows = route.request().postDataJSON().ingredients;
    api.ingredients.set(draft.version_id, rows);
    api.drafts.set(draft.version_id, { ...draft, edit_revision: 2 });
    await waiting; await route.fulfill({ json: { version_id: draft.version_id, edit_revision: 2, ingredients: rows } }); delivered();
  });
  await page.getByRole('button', { name: 'Save ingredients', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('unavailable');
  await expect(page.getByRole('textbox', { name: 'Ingredient 1 name', exact: true })).toHaveValue('Keep after failures');
  await page.getByRole('button', { name: 'Save ingredients', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('could not be completed', { timeout: 8000 });
  await page.getByRole('button', { name: 'Save ingredients', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Review saved ingredients', exact: true })).toBeVisible();
  release(); await finished;
  await page.getByRole('button', { name: 'Review saved ingredients', exact: true }).click();
  await page.getByRole('button', { name: 'Use saved ingredients', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Save ingredients', exact: true })).toBeDisabled();
  expect([...api.drafts.values()][0].edit_revision).toBe(2);
});
