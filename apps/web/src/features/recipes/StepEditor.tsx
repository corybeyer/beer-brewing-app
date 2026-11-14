import { useEffect, useRef, useState } from 'react';
import { Button, Card, SelectField, TextAreaField, TextField } from '@brewery/ui';
import { loadSteps, newCreationId, RecipeRequestError, saveSteps,
  type RecipeStep, type StepList } from '@brewery/communications/recipes';

type Props = { versionId: string; editRevision: number; disabled: boolean; onDirtyChange: (dirty: boolean) => void;
  onBusyChange: (busy: boolean) => void; onSaved: (steps: StepList) => void };
const problem = (error: unknown) => error instanceof RecipeRequestError ? error : new RecipeRequestError('unavailable', 'Recipe steps could not be loaded or saved. Please retry.');

export function StepEditor({ versionId, editRevision, disabled, onDirtyChange, onBusyChange, onSaved }: Props) {
  const [saved, setSaved] = useState<StepList | null>(null);
  const [rows, setRows] = useState<RecipeStep[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<RecipeRequestError | null>(null);
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState<StepList | null>(null);
  const [notice, setNotice] = useState('');
  const controller = useRef<AbortController | null>(null);
  const focusId = useRef<string | null>(null);
  const dirty = saved !== null && JSON.stringify(rows) !== JSON.stringify(saved.steps);
  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (saved && !dirty && saved.edit_revision !== editRevision) setSaved((current) => current ? { ...current, edit_revision: editRevision } : current);
  }, [dirty, editRevision, saved]);
  useEffect(() => { onBusyChange(busy); }, [busy, onBusyChange]);
  useEffect(() => () => { controller.current?.abort(); onDirtyChange(false); onBusyChange(false); }, [onDirtyChange, onBusyChange]);
  useEffect(() => { if (focusId.current) { document.getElementById(focusId.current)?.focus(); focusId.current = null; } }, [rows]);

  async function run(work: (signal: AbortSignal) => Promise<StepList>, apply: (value: StepList) => void) {
    controller.current?.abort(); const current = new AbortController(); controller.current = current;
    setBusy(true); setError(null); setNotice('');
    try { const value = await work(current.signal); if (!current.signal.aborted) apply(value); }
    catch (failure) { if (!current.signal.aborted) { const issue = problem(failure); setError(issue); if (issue.code === 'conflict') setConflict(true); } }
    finally { if (!current.signal.aborted) setBusy(false); }
  }
  function show(value: StepList) { setSaved(value); setRows(value.steps); setConflict(false); setLatest(null); }
  function load() { void run((signal) => loadSteps(versionId, signal), show); }
  useEffect(() => { load(); }, [versionId]);
  function update(index: number, change: Partial<RecipeStep>) {
    setRows((old) => old.map((row, position) => position === index ? { ...row, ...change } : row));
  }
  function fieldError(index: number, field: string) {
    return error?.issues.find((issue) => issue.path === `steps[${index}].${field}` || issue.path === `steps.${index}.${field}`)?.message;
  }
  const locked = disabled || busy;
  return <Card className="content-card" aria-label="Recipe steps" aria-busy={busy}>
    <h2>Steps</h2><p className="muted">Write the planned instructions and order. Dependencies and timing anchors keep their links when you reorder steps. This draft editor does not start timers or confirm actions.</p>
    {busy && <p aria-live="polite">Loading or saving recipe steps…</p>}
    {notice && <p role="status">{notice}</p>}
    {error && <div role="alert"><p>{error.message}</p>
      {error.issues.map((issue, index) => <p key={index}>{issue.path}: {issue.message}</p>)}
      {!saved && <Button variant="secondary" disabled={locked} onClick={load}>Retry loading steps</Button>}
      {conflict && <Button variant="secondary" disabled={locked} onClick={() => void run((signal) => loadSteps(versionId, signal), setLatest)}>Review saved steps</Button>}
    </div>}
    {latest && <Card className="content-card" aria-label="Latest saved steps"><h3>Latest saved steps</h3>
      {latest.steps.length === 0 ? <p>No steps saved.</p> : latest.steps.map((row, index) => <p key={row.id}>{index + 1}. {row.title || 'Untitled step'}</p>)}
      <div className="recipe-actions"><Button disabled={locked} onClick={() => { setSaved(latest); setLatest(null); setConflict(false); setError(null); }}>Keep my step changes</Button>
        <Button variant="secondary" disabled={locked} onClick={() => { show(latest); setError(null); }}>Use saved steps</Button></div>
    </Card>}
    <form className="recipe-form" onSubmit={(event) => { event.preventDefault(); if (saved && dirty && !locked && !conflict) void run((signal) => saveSteps(saved, rows, signal), (value) => { show(value); onSaved(value); setNotice('Steps saved.'); }); }}>
      {saved && rows.length === 0 && <p>No steps in this draft yet.</p>}
      {rows.map((row, index) => { const linked = saved?.linked_addition_step_ids.includes(row.id) || rows.some((candidate) => candidate.id !== row.id &&
        (candidate.anchor_step_id === row.id || candidate.dependencies.includes(row.id)));
        return <Card className="content-card recipe-form" key={row.id} aria-label={`Step ${index + 1}`}>
        <h3>Step {index + 1}</h3>
        <TextField id={`recipe-step-title-${row.id}`} label={`Step ${index + 1} title`} maxLength={200} value={row.title ?? ''} disabled={locked} error={fieldError(index, 'title')} onChange={(event) => update(index, { title: event.target.value || null })} />
        <TextAreaField label={`Step ${index + 1} instructions`} hint="Optional · up to 2,000 characters" maxLength={2000} value={row.instructions ?? ''} disabled={locked} error={fieldError(index, 'instructions')} onChange={(event) => update(index, { instructions: event.target.value || null })} />
        <div className="recipe-field"><p><strong>Must follow</strong></p>
          {rows.length < 2 ? <p className="muted">Add another step to define a dependency.</p> : <SelectField label={`Step ${index + 1} dependencies`} multiple size={Math.min(4, rows.length - 1)} value={row.dependencies} disabled={locked}
            aria-describedby={fieldError(index, 'dependencies') ? `step-dependencies-error-${row.id}` : undefined}
            aria-invalid={Boolean(fieldError(index, 'dependencies'))}
            onChange={(event) => update(index, { dependencies: Array.from(event.target.selectedOptions, (option) => option.value) })}>
            {rows.filter((candidate) => candidate.id !== row.id).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.title || `Step ${rows.findIndex((item) => item.id === candidate.id) + 1}`}</option>)}
          </SelectField>}
          {fieldError(index, 'dependencies') && <p id={`step-dependencies-error-${row.id}`} className="field-error">{fieldError(index, 'dependencies')}</p>}
        </div>
        <div className="recipe-field"><p><strong>Timing anchor</strong></p>
          <SelectField label={`Step ${index + 1} timing anchor`} value={row.anchor_step_id ?? ''} disabled={locked} onChange={(event) => update(index, { anchor_step_id: event.target.value || null })}>
            <option value="">No anchor</option>{rows.filter((candidate) => candidate.id !== row.id).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.title || `Step ${rows.findIndex((item) => item.id === candidate.id) + 1}`}</option>)}
          </SelectField>{fieldError(index, 'anchor_step_id') && <p className="field-error">{fieldError(index, 'anchor_step_id')}</p>}
        </div>
        <div className="recipe-actions">
          <Button variant="secondary" disabled={locked || index === 0} aria-label={`Move step ${index + 1} up`} onClick={() => setRows((old) => { const next = [...old]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; return next; })}>Move up</Button>
          <Button variant="secondary" disabled={locked || index === rows.length - 1} aria-label={`Move step ${index + 1} down`} onClick={() => setRows((old) => { const next = [...old]; [next[index], next[index + 1]] = [next[index + 1], next[index]]; return next; })}>Move down</Button>
          <Button variant="secondary" disabled={locked || linked} onClick={() => { focusId.current = 'add-recipe-step'; setRows((old) => old.filter((_, position) => position !== index)); }}>Remove step {index + 1}</Button>
          {linked && <p className="muted small">Remove this step’s dependent links and ingredient additions before deleting it.</p>}
        </div>
      </Card>; })}
      <div className="recipe-actions"><Button id="add-recipe-step" variant="secondary" disabled={locked || !saved || rows.length >= 100} onClick={() => {
        const id = newCreationId(); focusId.current = `recipe-step-title-${id}`;
        setRows((old) => [...old, { id, title: null, instructions: null, dependencies: [], anchor_step_id: null }]);
      }}>Add step</Button>
        <Button type="submit" busy={busy && dirty} disabled={!dirty || locked || conflict}>{busy ? 'Saving steps…' : 'Save steps'}</Button>
      </div>
      <p className="muted small" aria-live="polite">{dirty ? 'Unsaved changes' : 'Saved steps'}</p>
    </form>
  </Card>;
}
