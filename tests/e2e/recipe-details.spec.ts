import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { RecipeDetails, RecipeOverview, RecipeVolumeTarget } from '@brewery/communications/recipes';

const endpoint = '**/api/v1/recipe-drafts**';
const failure = (code: string, message: string, issues: { path: string; code: string; message: string }[] = []) => ({ error: { code, message, issues } });

async function server(page: Page, conflictOnce = false) {
  const drafts = new Map<string, RecipeOverview>();
  const details = new Map<string, RecipeDetails>();
  let conflictPending = conflictOnce;
  await page.route('**/api/v1/readiness', (route) => route.fulfill({ json: { status: 'ready' } }));
  await page.route(endpoint, async (route) => {
    const request = route.request(); const url = new URL(request.url());
    if (url.pathname === '/api/v1/recipe-drafts' && request.method() === 'POST') {
      const creationId = request.postDataJSON().creation_id as string;
      const draft: RecipeOverview = { recipe_id: creationId, version_id: `draft-${creationId}`, version_number: 1,
        name: null, description: null, edit_revision: 1, status: 'draft' };
      drafts.set(draft.version_id, draft);
      details.set(draft.version_id, { version_id: draft.version_id, edit_revision: 1, source: null, tags: [], volume_targets: [] });
      return route.fulfill({ status: 201, json: draft });
    }
    if (request.method() === 'PATCH' && url.pathname.endsWith('/details')) {
      const versionId = decodeURIComponent(url.pathname.split('/').at(-2)!);
      const current = details.get(versionId)!;
      const body = request.postDataJSON() as { expected_revision: number; source: string | null; tags: string[]; volume_targets: RecipeVolumeTarget[] };
      if (body.expected_revision !== current.edit_revision) return route.fulfill({ status: 409, json: failure('conflict', 'This draft changed elsewhere. Review the latest saved version before retrying.') });
      if (conflictPending) {
        conflictPending = false;
        details.set(versionId, { ...current, edit_revision: current.edit_revision + 1, source: 'A newer source', tags: ['latest'], volume_targets: [] });
        drafts.set(versionId, { ...drafts.get(versionId)!, edit_revision: current.edit_revision + 1 });
        return route.fulfill({ status: 409, json: failure('conflict', 'This draft changed elsewhere. Review the latest saved version before retrying.') });
      }
      const saved = { version_id: versionId, edit_revision: current.edit_revision + 1,
        source: body.source, tags: body.tags, volume_targets: body.volume_targets } satisfies RecipeDetails;
      details.set(versionId, saved); drafts.set(versionId, { ...drafts.get(versionId)!, edit_revision: saved.edit_revision });
      return route.fulfill({ json: saved });
    }
    if (request.method() === 'PATCH') {
      const versionId = decodeURIComponent(url.pathname.split('/').at(-2)!);
      const current = drafts.get(versionId)!; const body = request.postDataJSON();
      const saved = { ...current, name: body.name, description: body.description, edit_revision: current.edit_revision + 1 };
      drafts.set(versionId, saved); return route.fulfill({ json: saved });
    }
    if (url.pathname === '/api/v1/recipe-drafts') return route.fulfill({ json: { items: [...drafts.values()], next_offset: null } });
    if (url.pathname.endsWith('/details')) {
      const versionId = decodeURIComponent(url.pathname.split('/').at(-2)!);
      const value = details.get(versionId);
      return route.fulfill({ status: value ? 200 : 404, json: value ?? failure('not_found', 'This draft could not be found.') });
    }
    if (url.pathname.endsWith('/ingredients')) {
      const versionId = decodeURIComponent(url.pathname.split('/').at(-2)!);
      return route.fulfill({ json: { version_id: versionId, edit_revision: drafts.get(versionId)?.edit_revision ?? 1, ingredients: [] } });
    }
    if (url.pathname.endsWith('/steps')) {
      const versionId = decodeURIComponent(url.pathname.split('/').at(-2)!);
      return route.fulfill({ json: { version_id: versionId, edit_revision: drafts.get(versionId)?.edit_revision ?? 1, steps: [], linked_addition_step_ids: [] } });
    }
    if (url.pathname.endsWith('/conversion-proposals')) return route.fulfill({ json: [] });
    const versionId = decodeURIComponent(url.pathname.split('/').at(-1)!);
    const draft = drafts.get(versionId);
    return route.fulfill({ status: draft ? 200 : 404, json: draft ?? failure('not_found', 'This draft could not be found.') });
  });
  await page.route('**/api/v1/recipe-drafts/catalogue/grains', (route) => route.fulfill({ json: [] }));
  return { drafts, details };
}

async function newDraft(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'New recipe', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Recipe name', exact: true })).toBeFocused();
  await expect(page.getByRole('heading', { name: 'Recipe details', exact: true })).toBeVisible();
}

test('save and reload recipe source, tags, and purpose-specific volume targets', async ({ page }) => {
  const api = await server(page);
  await newDraft(page);
  await page.getByRole('textbox', { name: 'Source', exact: true }).fill('Grandfather’s notebook');
  await page.getByRole('button', { name: 'Add tag', exact: true }).click();
  await page.getByRole('textbox', { name: 'Tag 1', exact: true }).fill('summer');
  await page.getByRole('button', { name: 'Add tag', exact: true }).click();
  await page.getByRole('textbox', { name: 'Tag 2', exact: true }).fill('pale ale');
  await page.getByRole('button', { name: 'Add volume target', exact: true }).click();
  await page.getByRole('textbox', { name: 'Fermenter volume amount', exact: true }).fill('19');
  await page.getByRole('combobox', { name: 'Volume target 1 unit', exact: true }).selectOption('US_gal');
  await page.getByRole('button', { name: 'Add volume target', exact: true }).click();
  await page.getByRole('textbox', { name: 'Kettle volume amount', exact: true }).fill('23');
  await page.getByRole('combobox', { name: 'Volume target 2 unit', exact: true }).selectOption('L');
  await page.getByRole('button', { name: 'Save details', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Recipe details saved.' })).toBeVisible();
  const versionId = [...api.details.keys()][0];
  expect(api.details.get(versionId)).toEqual({ version_id: versionId, edit_revision: 2, source: 'Grandfather’s notebook',
    tags: ['summer', 'pale ale'], volume_targets: [
      { purpose: 'fermenter', amount: '19', unit: 'US_gal' }, { purpose: 'kettle', amount: '23', unit: 'L' },
    ] });
  await page.reload();
  await page.getByRole('button', { name: 'Open untitled draft', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Source', exact: true })).toHaveValue('Grandfather’s notebook');
  await expect(page.getByRole('textbox', { name: 'Tag 2', exact: true })).toHaveValue('pale ale');
  await expect(page.getByRole('textbox', { name: 'Fermenter volume amount', exact: true })).toHaveValue('19');
  await expect(page.getByRole('textbox', { name: 'Kettle volume amount', exact: true })).toHaveValue('23');
  await expect(page.getByRole('button', { name: 'Save details', exact: true })).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
});

test('a conflict review keeps my source and tags until I choose saved values', async ({ page }) => {
  await server(page, true);
  await newDraft(page);
  await page.getByRole('textbox', { name: 'Source', exact: true }).fill('My source');
  await page.getByRole('button', { name: 'Add tag', exact: true }).click();
  await page.getByRole('textbox', { name: 'Tag 1', exact: true }).fill('my tag');
  await page.getByRole('button', { name: 'Save details', exact: true }).click();
  await expect(page.getByRole('alert').getByText(/changed elsewhere/)).toBeVisible();
  await page.getByRole('button', { name: 'Review saved details', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Latest saved details', exact: true })).toBeVisible();
  await expect(page.getByText('Source: A newer source', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Keep my detail changes', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Source', exact: true })).toHaveValue('My source');
  await expect(page.getByRole('textbox', { name: 'Tag 1', exact: true })).toHaveValue('my tag');
  await expect(page.getByRole('button', { name: 'Save details', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Save details', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Recipe details saved.' })).toBeVisible();
});
