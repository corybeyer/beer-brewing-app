import { useEffect, useRef, useState } from 'react';
import { Button, Card, SelectField, TextField } from '@brewery/ui';
import { loadIngredients, newCreationId, RecipeRequestError, saveIngredients,
  type IngredientList, type RecipeIngredient } from '@brewery/communications/recipes';

type Props = { versionId: string; editRevision: number; disabled: boolean; onDirtyChange: (dirty: boolean) => void;
  onBusyChange: (busy: boolean) => void; onSaved: (list: IngredientList) => void };
const categories = ['grain', 'hops', 'yeast', 'other'];
const units = ['g', 'kg', 'oz', 'lb', 'mL', 'L', 'US_fl_oz', 'US_gal', 'count', 'packet'];
const problem = (error: unknown) => error instanceof RecipeRequestError ? error : new RecipeRequestError('unavailable', 'Ingredients could not be loaded or saved. Please retry.');

export function IngredientEditor({ versionId, editRevision, disabled, onDirtyChange, onBusyChange, onSaved }: Props) {
  const [saved, setSaved] = useState<IngredientList | null>(null);
  const [rows, setRows] = useState<RecipeIngredient[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<RecipeRequestError | null>(null);
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState<IngredientList | null>(null);
  const [notice, setNotice] = useState('');
  const controller = useRef<AbortController | null>(null);
  const focusId = useRef<string | null>(null);
  const dirty = saved !== null && JSON.stringify(rows) !== JSON.stringify(saved.ingredients);
  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (saved && !dirty && saved.edit_revision !== editRevision) setSaved((current) => current ? { ...current, edit_revision: editRevision } : current);
  }, [dirty, editRevision, saved]);
  useEffect(() => { onBusyChange(busy); }, [busy, onBusyChange]);
  useEffect(() => () => { controller.current?.abort(); onDirtyChange(false); onBusyChange(false); }, [onDirtyChange, onBusyChange]);
  useEffect(() => { if (focusId.current) { document.getElementById(focusId.current)?.focus(); focusId.current = null; } }, [rows]);

  async function run(work: (signal: AbortSignal) => Promise<IngredientList>, apply: (value: IngredientList) => void) {
    controller.current?.abort(); const current = new AbortController(); controller.current = current;
    setBusy(true); setError(null); setNotice('');
    try { const value = await work(current.signal); if (!current.signal.aborted) apply(value); }
    catch (failure) { if (!current.signal.aborted) { const issue = problem(failure); setError(issue); if (issue.code === 'conflict') setConflict(true); } }
    finally { if (!current.signal.aborted) setBusy(false); }
  }
  function show(value: IngredientList) { setSaved(value); setRows(value.ingredients); setConflict(false); setLatest(null); }
  function load() { void run((signal) => loadIngredients(versionId, signal), show); }
  useEffect(() => { load(); }, [versionId]); // Component is keyed by draft and successful overview save.
  function update(index: number, field: keyof RecipeIngredient, value: string) {
    setRows((old) => old.map((row, position) => position === index ? { ...row, [field]: value || null } : row));
  }
  function fieldError(index: number, field: string) {
    return error?.issues.find((issue) => issue.path === `ingredients[${index}].${field}` || issue.path === `ingredients.${index}.${field}`)?.message;
  }
  const locked = disabled || busy;
  return <Card className="content-card" aria-label="Recipe ingredients" aria-busy={busy}>
    <h2>Ingredients</h2><p className="muted">Plan the amounts you intend to use. Missing quantities and units can stay blank in a draft.</p>
    {busy && <p aria-live="polite">Loading or saving ingredients…</p>}
    {notice && <p role="status">{notice}</p>}
    {error && <div role="alert"><p>{error.message}</p>
      {error.issues.map((issue, index) => <p key={index}>{issue.path}: {issue.message}</p>)}
      {!saved && <Button variant="secondary" disabled={locked} onClick={load}>Retry loading ingredients</Button>}
      {conflict && <Button variant="secondary" disabled={locked} onClick={() => void run((signal) => loadIngredients(versionId, signal), setLatest)}>Review saved ingredients</Button>}
    </div>}
    {latest && <Card className="content-card" aria-label="Latest saved ingredients"><h3>Latest saved ingredients</h3>
      {latest.ingredients.length === 0 ? <p>No ingredients saved.</p> : latest.ingredients.map((row) => <p key={row.id}>{row.name ?? 'Unnamed ingredient'} · {row.quantity ?? 'No quantity'} {row.unit ?? 'No unit'}</p>)}
      <div className="recipe-actions"><Button disabled={locked} onClick={() => { setSaved(latest); setLatest(null); setConflict(false); setError(null); }}>Keep my ingredient changes</Button>
        <Button variant="secondary" disabled={locked} onClick={() => { show(latest); setError(null); }}>Use saved ingredients</Button></div>
    </Card>}
    <form className="recipe-form" onSubmit={(event) => { event.preventDefault(); if (saved && dirty && !locked && !conflict) void run((signal) => saveIngredients(saved, rows, signal), (value) => { show(value); onSaved(value); setNotice('Ingredients saved.'); }); }}>
      {saved && rows.length === 0 && <p>No ingredients in this draft yet.</p>}
      {rows.map((row, index) => <Card className="content-card recipe-form" key={row.id} aria-label={`Ingredient ${index + 1}`}>
        <h3>Ingredient {index + 1}</h3>
        <TextField id={`ingredient-name-${row.id}`} label={`Ingredient ${index + 1} name`} maxLength={200} value={row.name ?? ''} disabled={locked} error={fieldError(index, 'name')} onChange={(event) => update(index, 'name', event.target.value)} />
        <div className="recipe-field"><p><strong>Category</strong></p><SelectField label={`Ingredient ${index + 1} category`} value={row.category ?? ''} disabled={locked} aria-describedby={fieldError(index, 'category') ? `ingredient-category-error-${row.id}` : undefined} aria-invalid={Boolean(fieldError(index, 'category'))} onChange={(event) => update(index, 'category', event.target.value)}>
          <option value="">Not specified</option>{categories.map((category) => <option key={category} value={category}>{category}</option>)}
        </SelectField>
        {fieldError(index, 'category') && <p id={`ingredient-category-error-${row.id}`} className="field-error">{fieldError(index, 'category')}</p>}</div>
        <TextField label={`Ingredient ${index + 1} quantity`} inputMode="decimal" maxLength={25} hint="Optional · decimal amount, without unit conversion" value={row.quantity ?? ''} disabled={locked} error={fieldError(index, 'quantity')} onChange={(event) => update(index, 'quantity', event.target.value)} />
        <div className="recipe-field"><p><strong>Unit</strong></p><SelectField label={`Ingredient ${index + 1} unit`} value={row.unit ?? ''} disabled={locked} aria-describedby={fieldError(index, 'unit') ? `ingredient-unit-error-${row.id}` : undefined} aria-invalid={Boolean(fieldError(index, 'unit'))} onChange={(event) => update(index, 'unit', event.target.value)}>
          <option value="">Not specified</option>{units.map((unit) => <option key={unit} value={unit}>{unit}</option>)}
        </SelectField>
        {fieldError(index, 'unit') && <p id={`ingredient-unit-error-${row.id}`} className="field-error">{fieldError(index, 'unit')}</p>}</div>
        <Button variant="secondary" disabled={locked} onClick={() => { focusId.current = 'add-recipe-ingredient'; setRows((old) => old.filter((_, position) => position !== index)); }}>Remove ingredient {index + 1}</Button>
      </Card>)}
      <div className="recipe-actions"><Button id="add-recipe-ingredient" variant="secondary" disabled={locked || !saved || rows.length >= 100} onClick={() => {
        const id = newCreationId(); focusId.current = `ingredient-name-${id}`;
        setRows((old) => [...old, { id, name: null, category: null, quantity: null, unit: null }]);
      }}>Add ingredient</Button>
      <Button type="submit" disabled={locked || !dirty || conflict}>Save ingredients</Button>
      {dirty && saved && <Button variant="secondary" disabled={locked} onClick={() => { focusId.current = 'add-recipe-ingredient'; show(saved); setError(null); }}>Discard ingredient changes</Button>}</div>
      <p className="muted small" aria-live="polite">{dirty ? 'Unsaved ingredient changes' : 'Ingredient changes are saved only when you choose Save ingredients.'}</p>
    </form>
  </Card>;
}
