export interface RecipeOverview {
  recipe_id: string; version_id: string; version_number: number;
  name: string | null; description: string | null; edit_revision: number; status: 'draft';
}
export interface DraftPage { items: RecipeOverview[]; next_offset: number | null }
export interface FieldIssue { path: string; code: string; message: string }
export class RecipeRequestError extends Error {
  constructor(public code: string, message: string, public issues: FieldIssue[] = []) { super(message); }
}
const endpoint = '/api/v1/recipe-drafts';
const object = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const nullableText = (value: unknown) => value === null || typeof value === 'string';
const positiveInteger = (value: unknown) => Number.isSafeInteger(value) && Number(value) > 0;

export function parseOverview(value: unknown): RecipeOverview {
  if (!object(value) || typeof value.recipe_id !== 'string' || !value.recipe_id ||
      typeof value.version_id !== 'string' || !value.version_id || !positiveInteger(value.version_number) ||
      !positiveInteger(value.edit_revision) || value.status !== 'draft' || !nullableText(value.name) || !nullableText(value.description)) {
    throw new RecipeRequestError('invalid_response', 'The recipe service returned an unreadable draft. Please retry.');
  }
  return value as unknown as RecipeOverview;
}

async function request(path: string, signal: AbortSignal, method = 'GET', payload?: unknown): Promise<unknown> {
  try {
    const response = await fetch(path, { method, signal: AbortSignal.any([signal, AbortSignal.timeout(5000)]),
      cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'application/json',
        ...(payload === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: payload === undefined ? undefined : JSON.stringify(payload) });
    const value: unknown = await response.json();
    if (!response.ok) {
      if (object(value) && object(value.error) && typeof value.error.code === 'string' && typeof value.error.message === 'string') {
        const issues = Array.isArray(value.error.issues) ? value.error.issues.filter((issue): issue is FieldIssue =>
          object(issue) && typeof issue.path === 'string' && typeof issue.code === 'string' && typeof issue.message === 'string') : [];
        throw new RecipeRequestError(value.error.code, value.error.message, issues);
      }
      throw new RecipeRequestError('unavailable', 'Recipe storage is unavailable. Please retry.');
    }
    if (response.status !== 200 && response.status !== 201) throw new RecipeRequestError('invalid_response', 'The recipe service returned an unexpected response.');
    return value;
  } catch (error) {
    if (signal.aborted || error instanceof RecipeRequestError) throw error;
    throw new RecipeRequestError('unavailable', 'The request could not be completed. Your entered values are still here. Please retry.');
  }
}

export async function listDrafts(signal: AbortSignal, offset = 0): Promise<DraftPage> {
  const value = await request(`${endpoint}?limit=50&offset=${offset}`, signal);
  if (!object(value) || !Array.isArray(value.items) || value.items.length > 50 ||
      !(value.next_offset === null || Number.isSafeInteger(value.next_offset) && Number(value.next_offset) > offset && Number(value.next_offset) <= 100000)) {
    throw new RecipeRequestError('invalid_response', 'The recipe list could not be read. Please retry.');
  }
  return { items: value.items.map(parseOverview), next_offset: value.next_offset as number | null };
}

export function newCreationId(): string {
  // getRandomValues is available on the Pi's plain HTTP origin, unlike randomUUID.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
export async function createDraft(creationId: string, signal: AbortSignal): Promise<RecipeOverview> {
  const value = parseOverview(await request(endpoint, signal, 'POST', { creation_id: creationId }));
  if (value.recipe_id !== creationId.toLowerCase()) throw new RecipeRequestError('invalid_response', 'The created draft could not be verified. Retry with the same creation request.');
  return value;
}
export async function loadDraft(versionId: string, signal: AbortSignal): Promise<RecipeOverview> {
  const value = parseOverview(await request(`${endpoint}/${encodeURIComponent(versionId)}`, signal));
  if (value.version_id !== versionId) throw new RecipeRequestError('invalid_response', 'The returned draft does not match your selection. Please retry.');
  return value;
}
export async function saveOverview(draft: RecipeOverview, name: string, description: string, signal: AbortSignal): Promise<RecipeOverview> {
  const value = parseOverview(await request(`${endpoint}/${encodeURIComponent(draft.version_id)}/overview`, signal, 'PATCH', {
    expected_revision: draft.edit_revision, name: name.trim() || null, description: description || null,
  }));
  if (value.version_id !== draft.version_id || value.recipe_id !== draft.recipe_id || value.version_number !== draft.version_number || value.edit_revision !== draft.edit_revision + 1) {
    throw new RecipeRequestError('invalid_response', 'The save response could not be verified. Review the latest saved version before retrying.');
  }
  return value;
}

export interface RecipeIngredient { id: string; name: string | null; category: string | null; quantity: string | null; unit: string | null }
export interface IngredientList { version_id: string; edit_revision: number; ingredients: RecipeIngredient[] }
function parseIngredients(value: unknown, versionId: string): IngredientList {
  if (!object(value) || value.version_id !== versionId || !positiveInteger(value.edit_revision) || !Array.isArray(value.ingredients) ||
      !value.ingredients.every((row) => object(row) && typeof row.id === 'string' && row.id.length > 0 &&
        nullableText(row.name) && nullableText(row.category) && nullableText(row.unit) &&
        (row.quantity === null || typeof row.quantity === 'string' && /^[0-9]+(?:\.[0-9]+)?$/.test(row.quantity))) ||
      new Set(value.ingredients.map((row) => (row as RecipeIngredient).id)).size !== value.ingredients.length) {
    throw new RecipeRequestError('invalid_response', 'The ingredient list could not be read. Please retry.');
  }
  return value as unknown as IngredientList;
}
export async function loadIngredients(versionId: string, signal: AbortSignal): Promise<IngredientList> {
  return parseIngredients(await request(`${endpoint}/${encodeURIComponent(versionId)}/ingredients`, signal), versionId);
}
export async function saveIngredients(current: IngredientList, ingredients: RecipeIngredient[], signal: AbortSignal): Promise<IngredientList> {
  const saved = parseIngredients(await request(`${endpoint}/${encodeURIComponent(current.version_id)}/ingredients`, signal, 'PATCH', {
    expected_revision: current.edit_revision, ingredients,
  }), current.version_id);
  if (saved.edit_revision !== current.edit_revision + 1) throw new RecipeRequestError('invalid_response', 'The ingredient save could not be verified. Review the saved list before retrying.');
  return saved;
}

export interface GrainProfile {
  revision_id: string; name: string; manufacturer: string | null; potential_ppg: string | null;
  potential_status: string; potential_note: string | null; source_url: string | null; flavor_notes: string | null;
  flavor_tags: string[]; source_label: string; source_retrieved_at: string;
}
export interface ConversionPreview {
  proposal_id: string; source_ingredient_id: string; target_ingredient_id: string; target_name: string;
  target_unit: string; target_amount: string; exact_amount_numerator: string; exact_amount_denominator: string;
  gravity_points_numerator: string; gravity_points_denominator: string; comparison_point: string; weighing_note: string;
}
function parseConversion(value: unknown): ConversionPreview {
  const fields = ['proposal_id', 'source_ingredient_id', 'target_ingredient_id', 'target_name', 'target_unit',
    'target_amount', 'exact_amount_numerator', 'exact_amount_denominator', 'gravity_points_numerator',
    'gravity_points_denominator', 'comparison_point', 'weighing_note'] as const;
  if (!object(value) || fields.some((key) => typeof value[key] !== 'string' || !value[key])) {
    throw new RecipeRequestError('invalid_response', 'The conversion preview could not be verified. Please retry.');
  }
  return value as unknown as ConversionPreview;
}
export async function listGrainProfiles(signal: AbortSignal): Promise<GrainProfile[]> {
  const value = await request(`${endpoint}/catalogue/grains`, signal);
  if (!Array.isArray(value) || value.length > 1000 || !value.every((profile) => object(profile) &&
      typeof profile.revision_id === 'string' && typeof profile.name === 'string' &&
      nullableText(profile.manufacturer) && nullableText(profile.potential_ppg) &&
      typeof profile.potential_status === 'string' && nullableText(profile.potential_note) &&
      nullableText(profile.source_url) &&
      nullableText(profile.flavor_notes) && Array.isArray(profile.flavor_tags) &&
      profile.flavor_tags.every((tag) => typeof tag === 'string') && typeof profile.source_label === 'string' &&
      typeof profile.source_retrieved_at === 'string')) {
    throw new RecipeRequestError('invalid_response', 'The grain catalogue could not be read. Please retry.');
  }
  return value as GrainProfile[];
}
export async function createConversionPreview(versionId: string, input: Record<string, string | number | null>, signal: AbortSignal): Promise<ConversionPreview> {
  return parseConversion(await request(`${endpoint}/${encodeURIComponent(versionId)}/conversion-proposals`, signal, 'POST', input));
}
export async function loadConversionPreview(versionId: string, proposalId: string, signal: AbortSignal): Promise<ConversionPreview> {
  return parseConversion(await request(`${endpoint}/${encodeURIComponent(versionId)}/conversion-proposals/${encodeURIComponent(proposalId)}`, signal));
}
export async function applyConversion(versionId: string, proposalId: string, expectedRevision: number, signal: AbortSignal): Promise<RecipeOverview> {
  return parseOverview(await request(`${endpoint}/${encodeURIComponent(versionId)}/conversion-proposals/${encodeURIComponent(proposalId)}/apply`, signal, 'POST', { expected_revision: expectedRevision }));
}

export interface RecipeStep { id: string; title: string | null; instructions: string | null;
  dependencies: string[]; anchor_step_id: string | null }
export interface StepList { version_id: string; edit_revision: number; steps: RecipeStep[]; linked_addition_step_ids: string[] }
function parseSteps(value: unknown, versionId: string): StepList {
  if (!object(value) || value.version_id !== versionId || !positiveInteger(value.edit_revision) ||
      !Array.isArray(value.steps) || !Array.isArray(value.linked_addition_step_ids)) {
    throw new RecipeRequestError('invalid_response', 'The recipe steps could not be read. Please retry.');
  }
  const steps = value.steps;
  const linked = value.linked_addition_step_ids;
  if (!linked.every((id) => typeof id === 'string' && id.length > 0) ||
      !steps.every((step) => object(step) && typeof step.id === 'string' && step.id.length > 0 &&
        nullableText(step.title) && nullableText(step.instructions) && nullableText(step.anchor_step_id) &&
        Array.isArray(step.dependencies) && step.dependencies.every((id) => typeof id === 'string' && id.length > 0) &&
        new Set(step.dependencies).size === step.dependencies.length) ||
      new Set(steps.map((step) => (step as RecipeStep).id)).size !== steps.length ||
      new Set(linked).size !== linked.length ||
      linked.some((id) => !steps.some((step) => object(step) && step.id === id))) {
    throw new RecipeRequestError('invalid_response', 'The recipe steps could not be read. Please retry.');
  }
  return value as unknown as StepList;
}
export async function loadSteps(versionId: string, signal: AbortSignal): Promise<StepList> {
  return parseSteps(await request(`${endpoint}/${encodeURIComponent(versionId)}/steps`, signal), versionId);
}
export async function saveSteps(current: StepList, steps: RecipeStep[], signal: AbortSignal): Promise<StepList> {
  const saved = parseSteps(await request(`${endpoint}/${encodeURIComponent(current.version_id)}/steps`, signal, 'PATCH', {
    expected_revision: current.edit_revision, steps,
  }), current.version_id);
  if (saved.edit_revision !== current.edit_revision + 1) throw new RecipeRequestError('invalid_response', 'The step save could not be verified. Review the latest saved steps before retrying.');
  return saved;
}
