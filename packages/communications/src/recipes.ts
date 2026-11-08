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
