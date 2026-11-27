import { useEffect, useRef, useState } from 'react';
import { Button, Card, SelectField, TextAreaField, TextField } from '@brewery/ui';
import { loadSteps, maxStepAdditions, newCreationId, RecipeRequestError, saveSteps,
  type RecipeIngredient, type RecipeStep, type StepAddition, type StepList } from '@brewery/communications/recipes';

type Props = { versionId: string; editRevision: number; disabled: boolean; onDirtyChange: (dirty: boolean) => void;
  onBusyChange: (busy: boolean) => void; onSaved: (steps: StepList) => void };
const problem = (error: unknown) => error instanceof RecipeRequestError ? error : new RecipeRequestError('unavailable', 'Recipe steps could not be loaded or saved. Please retry.');
type PortionRow = { key: string; value: StepAddition };
const portionRows = (items: StepAddition[]): PortionRow[] => items.map((value) => ({ key: newCreationId(), value }));

function ingredientLabel(item: RecipeIngredient, index: number) {
  const total = item.quantity !== null && item.unit ? `${item.quantity} ${item.unit} total` : 'total or unit missing';
  return `${index + 1}. ${item.name || 'Unnamed ingredient'} · ${total}`;
}

export function StepEditor({ versionId, editRevision, disabled, onDirtyChange, onBusyChange, onSaved }: Props) {
  const [saved, setSaved] = useState<StepList | null>(null);
  const [rows, setRows] = useState<RecipeStep[]>([]);
  const [portions, setPortions] = useState<PortionRow[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<RecipeRequestError | null>(null);
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState<StepList | null>(null);
  const [notice, setNotice] = useState('');
  const controller = useRef<AbortController | null>(null);
  const focusId = useRef<string | null>(null);
  const additions = portions.map((portion) => portion.value);
  const portionsDirty = saved !== null && JSON.stringify(additions) !== JSON.stringify(saved.additions);
  const stepsDirty = saved !== null && JSON.stringify(rows) !== JSON.stringify(saved.steps);
  const dirty = portionsDirty || stepsDirty;
  const outdated = saved !== null && !dirty && saved.edit_revision < editRevision;
  const reviewSteps = latest && !stepsDirty ? latest.steps : rows;
  const reviewStepIds = new Set(reviewSteps.map((step) => step.id));
  const reviewAdditions = latest && !portionsDirty ? latest.additions : additions;
  const reviewHasMissingStep = latest !== null && reviewAdditions.some((item) => !reviewStepIds.has(item.step_id));
  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => { onBusyChange(busy); }, [busy, onBusyChange]);
  useEffect(() => () => { controller.current?.abort(); onDirtyChange(false); onBusyChange(false); }, [onDirtyChange, onBusyChange]);
  useEffect(() => { if (focusId.current) { document.getElementById(focusId.current)?.focus(); focusId.current = null; } }, [rows, portions]);

  async function run(work: (signal: AbortSignal) => Promise<StepList>, apply: (value: StepList) => void) {
    controller.current?.abort(); const current = new AbortController(); controller.current = current;
    setBusy(true); setError(null); setNotice('');
    try { const value = await work(current.signal); if (!current.signal.aborted) apply(value); }
    catch (failure) { if (!current.signal.aborted) { const issue = problem(failure); setError(issue); if (issue.code === 'conflict') setConflict(true); } }
    finally { if (!current.signal.aborted) setBusy(false); }
  }
  function show(value: StepList) {
    setSaved(value); setRows(value.steps); setPortions(portionRows(value.additions)); setConflict(false); setLatest(null);
  }
  function load(minimumRevision = 1) {
    void run(async (signal) => {
      const value = await loadSteps(versionId, signal);
      if (value.edit_revision < minimumRevision) {
        throw new RecipeRequestError('invalid_response', 'The latest recipe steps could not be read. Please retry.');
      }
      return value;
    }, show);
  }
  useEffect(() => { load(); }, [versionId]);
  useEffect(() => { if (outdated && !busy && !error) load(editRevision); }, [outdated, busy, error, editRevision]);
  function update(index: number, change: Partial<RecipeStep>) {
    setRows((old) => old.map((row, position) => position === index ? { ...row, ...change } : row));
  }
  function fieldError(index: number, field: string, collection = 'steps') {
    return error?.issues.find((issue) =>
      issue.path === `${collection}[${index}].${field}` || issue.path === `${collection}.${index}.${field}`)?.message;
  }
  function updatePortion(key: string, change: Partial<StepAddition>) {
    setPortions((current) => current.map((row) => row.key === key ? { ...row, value: { ...row.value, ...change } } : row));
  }
  const locked = disabled || busy;
  const formLocked = locked || outdated;
  const ingredients = saved?.ingredients ?? [];
  return <Card className="content-card" aria-label="Recipe steps" aria-busy={busy}>
    <h2>Steps</h2><p className="muted">Plan instructions, dependencies, timing anchors, and ingredient portions. Reordering steps keeps their links.</p>
    {busy && <p aria-live="polite">Loading or saving recipe steps…</p>}
    {notice && <p role="status">{notice}</p>}
    {error && <div role="alert"><p>{error.message}</p>
      {error.issues.map((issue, index) => <p key={index}>{issue.path}: {issue.message}</p>)}
      {(!saved || outdated) && <Button variant="secondary" disabled={locked} onClick={() => load(editRevision)}>Retry loading steps</Button>}
      {conflict && <Button variant="secondary" disabled={locked} onClick={() => void run((signal) => loadSteps(versionId, signal), setLatest)}>Review saved steps</Button>}
    </div>}
    {latest && <Card className="content-card" aria-label="Latest saved steps"><h3>Latest saved steps</h3>
      {latest.steps.length === 0 ? <p>No steps saved.</p> : latest.steps.map((row, index) => <div key={row.id}>
        <p>{index + 1}. {row.title || 'Untitled step'}</p>
        {latest.additions.map((item, position) => item.step_id === row.id && <p key={position}>
          {latest.ingredients.find((ingredient) => ingredient.id === item.ingredient_id)?.name || 'Unnamed ingredient'}
          {' · '}{item.quantity === null ? 'Amount pending' : [item.quantity, item.unit].filter(Boolean).join(' ')}
        </p>)}
      </div>)}
      {reviewHasMissingStep && <p>A portion is linked to a step missing from the plan you would keep. Resolve the link in your changes or use the saved plan.</p>}
      <div className="recipe-actions"><Button disabled={locked || reviewHasMissingStep} onClick={() => {
        if (!stepsDirty) setRows(latest.steps);
        if (!portionsDirty) setPortions(portionRows(latest.additions));
        setSaved(latest); setLatest(null); setConflict(false); setError(null);
      }}>{portionsDirty ? stepsDirty ? 'Keep my step and portion changes' : 'Keep my portion changes' : 'Keep my step changes'}</Button>
        <Button variant="secondary" disabled={locked} onClick={() => { show(latest); setError(null); }}>Use saved steps</Button></div>
    </Card>}
    <form className="recipe-form" onSubmit={(event) => {
      event.preventDefault();
      if (saved && dirty && !formLocked && !conflict) {
        void run((signal) => saveSteps(saved, rows, signal, portionsDirty ? additions : undefined), (value) => {
          show(value); onSaved(value); setNotice('Steps saved.');
        });
      }
    }}>
      {saved && rows.length === 0 && <p>No steps in this draft yet.</p>}
      {rows.map((row, index) => { const linked = additions.some((item) => item.step_id === row.id) || rows.some((candidate) => candidate.id !== row.id &&
        (candidate.anchor_step_id === row.id || candidate.dependencies.includes(row.id)));
        return <Card className="content-card recipe-form" key={row.id} aria-label={`Step ${index + 1}`}>
        <h3>Step {index + 1}</h3>
        <TextField id={`recipe-step-title-${row.id}`} label={`Step ${index + 1} title`} maxLength={200} value={row.title ?? ''} disabled={formLocked} error={fieldError(index, 'title')} onChange={(event) => update(index, { title: event.target.value || null })} />
        <TextAreaField label={`Step ${index + 1} instructions`} hint="Optional · up to 2,000 characters" maxLength={2000} value={row.instructions ?? ''} disabled={formLocked} error={fieldError(index, 'instructions')} onChange={(event) => update(index, { instructions: event.target.value || null })} />
        <div className="recipe-field"><p><strong>Must follow</strong></p>
          {rows.length < 2 ? <p className="muted">Add another step to define a dependency.</p> : <SelectField label={`Step ${index + 1} dependencies`} multiple size={Math.min(4, rows.length - 1)} value={row.dependencies} disabled={formLocked}
            aria-describedby={fieldError(index, 'dependencies') ? `step-dependencies-error-${row.id}` : undefined}
            aria-invalid={Boolean(fieldError(index, 'dependencies'))}
            onChange={(event) => update(index, { dependencies: Array.from(event.target.selectedOptions, (option) => option.value) })}>
            {rows.filter((candidate) => candidate.id !== row.id).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.title || `Step ${rows.findIndex((item) => item.id === candidate.id) + 1}`}</option>)}
          </SelectField>}
          {fieldError(index, 'dependencies') && <p id={`step-dependencies-error-${row.id}`} className="field-error">{fieldError(index, 'dependencies')}</p>}
        </div>
        <div className="recipe-field"><p><strong>Timing anchor</strong></p>
          <SelectField label={`Step ${index + 1} timing anchor`} value={row.anchor_step_id ?? ''} disabled={formLocked} onChange={(event) => update(index, { anchor_step_id: event.target.value || null })}>
            <option value="">No anchor</option>{rows.filter((candidate) => candidate.id !== row.id).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.title || `Step ${rows.findIndex((item) => item.id === candidate.id) + 1}`}</option>)}
          </SelectField>{fieldError(index, 'anchor_step_id') && <p className="field-error">{fieldError(index, 'anchor_step_id')}</p>}
        </div>
        <div className="recipe-form">
          <h4>Ingredient portions</h4>
          {ingredients.length === 0 && <p className="muted">Save ingredients to assign them to this step.</p>}
          {portions.map((portion, position) => ({ portion, position })).filter(({ portion }) => portion.value.step_id === row.id).map(({ portion, position }, ordinal) => {
            const ingredientIndex = ingredients.findIndex((item) => item.id === portion.value.ingredient_id);
            const ingredient = ingredients[ingredientIndex];
            const canEnterAmount = ingredient?.quantity != null && ingredient.unit != null;
            const label = `Step ${index + 1} portion ${ordinal + 1}`;
            const ingredientError = fieldError(position, 'ingredient_id', 'additions');
            return <div className="recipe-field" key={portion.key}>
              <SelectField id={`portion-${portion.key}`} label={`${label} ingredient`} value={portion.value.ingredient_id} disabled={formLocked}
                aria-invalid={Boolean(ingredientError)} aria-describedby={ingredientError ? `portion-error-${portion.key}` : undefined}
                onChange={(event) => {
                  const item = ingredients.find((candidate) => candidate.id === event.target.value);
                  if (item) updatePortion(portion.key, { ingredient_id: item.id, quantity: null, unit: item.unit });
                }}>
                {!ingredient && <option value={portion.value.ingredient_id}>Ingredient no longer saved</option>}
                {ingredients.map((item, ingredientIndex) => <option key={item.id} value={item.id}>{ingredientLabel(item, ingredientIndex)}</option>)}
              </SelectField>
              {ingredientError && <p id={`portion-error-${portion.key}`} className="field-error">{ingredientError}</p>}
              <TextField label={`${label} amount`} inputMode="decimal" value={portion.value.quantity ?? ''}
                hint={canEnterAmount ? `${ingredient.unit} · leave blank if the amount is pending` : 'Save the ingredient total and unit to assign an amount.'}
                disabled={formLocked || (!canEnterAmount && portion.value.quantity === null)}
                error={fieldError(position, 'quantity', 'additions') || fieldError(position, 'unit', 'additions') ||
                  fieldError(ingredientIndex, 'quantity', 'ingredients')}
                onChange={(event) => updatePortion(portion.key, { quantity: event.target.value || null, unit: ingredient?.unit ?? null })} />
              <Button variant="secondary" disabled={formLocked} onClick={() => {
                focusId.current = `add-portion-${row.id}`;
                setPortions((current) => current.filter((item) => item.key !== portion.key));
              }}>Remove {label.toLowerCase()}</Button>
            </div>;
          })}
          <Button id={`add-portion-${row.id}`} variant="secondary"
            disabled={formLocked || ingredients.length === 0 || portions.length >= maxStepAdditions}
            onClick={() => {
              const item = ingredients[0];
              const key = newCreationId();
              focusId.current = `portion-${key}`;
              setPortions((current) => [...current, { key, value: { step_id: row.id, ingredient_id: item.id, quantity: null, unit: item.unit } }]);
            }}>Add portion to step {index + 1}</Button>
        </div>
        <div className="recipe-actions">
          <Button variant="secondary" disabled={formLocked || index === 0} aria-label={`Move step ${index + 1} up`} onClick={() => setRows((old) => { const next = [...old]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; return next; })}>Move up</Button>
          <Button variant="secondary" disabled={formLocked || index === rows.length - 1} aria-label={`Move step ${index + 1} down`} onClick={() => setRows((old) => { const next = [...old]; [next[index], next[index + 1]] = [next[index + 1], next[index]]; return next; })}>Move down</Button>
          <Button variant="secondary" disabled={formLocked || linked} onClick={() => { focusId.current = 'add-recipe-step'; setRows((old) => old.filter((_, position) => position !== index)); }}>Remove step {index + 1}</Button>
          {linked && <p className="muted small">Remove this step’s dependent links and ingredient additions before deleting it.</p>}
        </div>
      </Card>; })}
      <div className="recipe-actions"><Button id="add-recipe-step" variant="secondary" disabled={formLocked || !saved || rows.length >= 100} onClick={() => {
        const id = newCreationId(); focusId.current = `recipe-step-title-${id}`;
        setRows((old) => [...old, { id, title: null, instructions: null, dependencies: [], anchor_step_id: null }]);
      }}>Add step</Button>
        <Button type="submit" busy={busy && dirty} disabled={!dirty || formLocked || conflict}>{busy ? 'Saving steps…' : 'Save steps'}</Button>
      </div>
      <p className="muted small" aria-live="polite">{dirty ? 'Unsaved changes' : 'Saved steps'}</p>
    </form>
  </Card>;
}
