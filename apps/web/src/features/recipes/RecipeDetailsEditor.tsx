import { useEffect, useRef, useState } from 'react';
import { Button, Card, SelectField, TextField } from '@brewery/ui';
import { loadRecipeDetails, newCreationId, RecipeRequestError, saveRecipeDetails,
  type RecipeDetails, type RecipeVolumeTarget } from '@brewery/communications/recipes';
import './RecipeDetailsEditor.css';

type TargetDraft = RecipeVolumeTarget & { key: string };
type DetailsInput = { source: string | null; tags: string[]; volume_targets: RecipeVolumeTarget[] };
type Props = { versionId: string; editRevision: number; disabled: boolean; onDirtyChange: (dirty: boolean) => void;
  onBusyChange: (busy: boolean) => void; onSaved: (details: RecipeDetails) => void };

const purposes: { value: RecipeVolumeTarget['purpose']; label: string }[] = [
  { value: 'fermenter', label: 'Fermenter volume' },
  { value: 'kettle', label: 'Kettle volume' },
  { value: 'packaged', label: 'Packaged volume' },
];
const volumeUnits: RecipeVolumeTarget['unit'][] = ['mL', 'L', 'US_fl_oz', 'US_gal'];
const problem = (error: unknown) => error instanceof RecipeRequestError
  ? error : new RecipeRequestError('unavailable', 'Recipe details could not be loaded or saved. Please retry.');
const targetRows = (targets: RecipeVolumeTarget[]): TargetDraft[] => targets.map((target) => ({ ...target, key: newCreationId() }));
const savedDetailsInput = (details: RecipeDetails): DetailsInput => ({
  source: details.source,
  tags: details.tags,
  volume_targets: details.volume_targets,
});
const toInput = (source: string, tags: string[], targets: TargetDraft[]): DetailsInput => ({
  source: source.trim() || null,
  tags: tags.map((tag) => tag.trim()),
  volume_targets: targets.map(({ purpose, amount, unit }) => ({ purpose, amount: amount.trim(), unit })),
});

export function RecipeDetailsEditor({ versionId, editRevision, disabled, onDirtyChange, onBusyChange, onSaved }: Props) {
  const [saved, setSaved] = useState<RecipeDetails | null>(null);
  const [source, setSource] = useState('');
  const [tags, setTags] = useState<{ key: string; value: string }[]>([]);
  const [targets, setTargets] = useState<TargetDraft[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<RecipeRequestError | null>(null);
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState<RecipeDetails | null>(null);
  const [notice, setNotice] = useState('');
  const controller = useRef<AbortController | null>(null);
  const focusId = useRef<string | null>(null);
  const savedInput = saved && savedDetailsInput(saved);
  const currentInput = toInput(source, tags.map((tag) => tag.value), targets);
  const dirty = savedInput !== null && JSON.stringify(currentInput) !== JSON.stringify(savedInput);
  const incomplete = tags.some((tag) => !tag.value.trim()) || targets.some((target) => !target.amount.trim());

  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (saved && !dirty && saved.edit_revision !== editRevision) setSaved((current) => current ? { ...current, edit_revision: editRevision } : current);
  }, [dirty, editRevision, saved]);
  useEffect(() => { onBusyChange(busy); }, [busy, onBusyChange]);
  useEffect(() => () => { controller.current?.abort(); onDirtyChange(false); onBusyChange(false); }, [onDirtyChange, onBusyChange]);
  useEffect(() => { if (focusId.current) { document.getElementById(focusId.current)?.focus(); focusId.current = null; } }, [tags, targets]);

  async function run(work: (signal: AbortSignal) => Promise<RecipeDetails>, apply: (value: RecipeDetails) => void) {
    controller.current?.abort(); const current = new AbortController(); controller.current = current;
    setBusy(true); setError(null); setNotice('');
    try { const value = await work(current.signal); if (!current.signal.aborted) apply(value); }
    catch (failure) { if (!current.signal.aborted) { const issue = problem(failure); setError(issue); if (issue.code === 'conflict') setConflict(true); } }
    finally { if (!current.signal.aborted) setBusy(false); }
  }
  function show(value: RecipeDetails) {
    setSaved(value); setSource(value.source ?? ''); setTags(value.tags.map((tag) => ({ key: newCreationId(), value: tag })));
    setTargets(targetRows(value.volume_targets)); setConflict(false); setLatest(null);
  }
  function load() { void run((signal) => loadRecipeDetails(versionId, signal), show); }
  useEffect(() => { load(); }, [versionId]);

  function issue(path: string) {
    return error?.issues.find((item) => item.path === path || item.path === path.replace(/\[(\d+)\]/g, '.$1'))?.message;
  }
  function updateTag(key: string, value: string) {
    setTags((rows) => rows.map((row) => row.key === key ? { ...row, value } : row));
  }
  function updateTarget(key: string, change: Partial<RecipeVolumeTarget>) {
    setTargets((rows) => rows.map((row) => row.key === key ? { ...row, ...change } : row));
  }
  function availablePurposes(target: TargetDraft) {
    return purposes.filter((purpose) => purpose.value === target.purpose || !targets.some((row) => row.key !== target.key && row.purpose === purpose.value));
  }
  const locked = disabled || busy;
  const availablePurpose = purposes.find((purpose) => !targets.some((target) => target.purpose === purpose.value));

  return <Card className="content-card" aria-label="Recipe details" aria-busy={busy}>
    <h2>Recipe details</h2>
    <p className="muted">Keep notes about where the recipe came from, add descriptive tags, and record optional volume targets. Blank values are not treated as zero.</p>
    {busy && <p aria-live="polite">Loading or saving recipe details…</p>}
    {notice && <p role="status">{notice}</p>}
    {error && <div role="alert"><p>{error.message}</p>
      {error.issues.map((item, index) => <p key={`${item.path}-${index}`}>{item.path}: {item.message}</p>)}
      {!saved && <Button variant="secondary" disabled={locked} onClick={load}>Retry loading recipe details</Button>}
      {conflict && <Button variant="secondary" disabled={locked} onClick={() => void run((signal) => loadRecipeDetails(versionId, signal), setLatest)}>Review saved details</Button>}
    </div>}
    {latest && <Card className="content-card" aria-label="Latest saved recipe details">
      <h3>Latest saved details</h3><p>Source: {latest.source || 'Not specified'}</p>
      <p>Tags: {latest.tags.length ? latest.tags.join(', ') : 'None'}</p>
      {latest.volume_targets.length ? latest.volume_targets.map((target) => <p key={target.purpose}>{purposes.find((item) => item.value === target.purpose)?.label}: {target.amount} {target.unit}</p>) : <p>No volume targets.</p>}
      <div className="recipe-actions"><Button disabled={locked} onClick={() => { setSaved(latest); onSaved(latest); setConflict(false); setLatest(null); setError(null); }}>Keep my detail changes</Button>
        <Button variant="secondary" disabled={locked} onClick={() => { show(latest); setError(null); }}>Use saved details</Button></div>
    </Card>}
    <form className="recipe-form" onSubmit={(event) => {
      event.preventDefault();
      if (saved && dirty && !incomplete && !locked && !conflict) void run(
        (signal) => saveRecipeDetails(saved, currentInput, signal),
        (value) => { show(value); onSaved(value); setNotice('Recipe details saved.'); });
    }}>
      <TextField label="Source" hint="Optional · book, person, website, or your own notes · up to 2,000 characters" maxLength={2000} value={source} disabled={locked}
        error={issue('source')} onChange={(event) => setSource(event.target.value)} />

      <div className="recipe-field" aria-label="Recipe tags">
        <h3>Tags</h3><p className="muted">Add words that describe this recipe.</p>
        {tags.length === 0 && <p>No tags added.</p>}
        {tags.map((tag, index) => <div className="recipe-details-tag" key={tag.key}>
          <TextField id={`recipe-detail-tag-${tag.key}`} label={`Tag ${index + 1}`} maxLength={100} value={tag.value} disabled={locked}
            error={issue(`tags[${index}]`)} onChange={(event) => updateTag(tag.key, event.target.value)} />
          <Button variant="secondary" disabled={locked} onClick={() => { focusId.current = 'add-recipe-detail-tag'; setTags((rows) => rows.filter((row) => row.key !== tag.key)); }}>Remove tag {index + 1}</Button>
        </div>)}
        <Button id="add-recipe-detail-tag" variant="secondary" disabled={locked || tags.length >= 32} onClick={() => {
          const key = newCreationId(); focusId.current = `recipe-detail-tag-${key}`;
          setTags((rows) => [...rows, { key, value: '' }]);
        }}>Add tag</Button>
      </div>

      <div className="recipe-field" aria-label="Volume targets">
        <h3>Volume targets</h3><p className="muted">Optional targets are kept separate by purpose. Enter an amount and unit only when known.</p>
        {targets.length === 0 && <p>No volume targets added.</p>}
        <div className="recipe-details-targets">
          {targets.map((target, index) => <Card className="recipe-details-target content-card" key={target.key} aria-label={`Volume target ${index + 1}`}>
            <div className="recipe-field"><p><strong>Purpose</strong></p>
              <SelectField label={`Volume target ${index + 1} purpose`} value={target.purpose} disabled={locked}
                onChange={(event) => updateTarget(target.key, { purpose: event.target.value as RecipeVolumeTarget['purpose'] })}>
                {availablePurposes(target).map((purpose) => <option key={purpose.value} value={purpose.value}>{purpose.label}</option>)}
              </SelectField>
            </div>
            <TextField id={`recipe-volume-target-${target.key}`} label={`${purposes.find((purpose) => purpose.value === target.purpose)?.label ?? 'Volume'} amount`} inputMode="decimal" maxLength={32}
              value={target.amount} disabled={locked} error={issue(`volume_targets[${index}].amount`)} onChange={(event) => updateTarget(target.key, { amount: event.target.value })} />
            <div className="recipe-field"><p><strong>Unit</strong></p>
              <SelectField label={`Volume target ${index + 1} unit`} value={target.unit} disabled={locked}
                aria-describedby={issue(`volume_targets[${index}].unit`) ? `volume-unit-error-${target.key}` : undefined}
                aria-invalid={Boolean(issue(`volume_targets[${index}].unit`))}
                onChange={(event) => updateTarget(target.key, { unit: event.target.value as RecipeVolumeTarget['unit'] })}>
                {volumeUnits.map((unit) => <option key={unit} value={unit}>{unit}</option>)}
              </SelectField>
              {issue(`volume_targets[${index}].unit`) && <p id={`volume-unit-error-${target.key}`} className="field-error">{issue(`volume_targets[${index}].unit`)}</p>}
            </div>
            <Button variant="secondary" disabled={locked} onClick={() => { focusId.current = 'add-recipe-volume-target'; setTargets((rows) => rows.filter((row) => row.key !== target.key)); }}>Remove volume target {index + 1}</Button>
          </Card>)}
        </div>
        <Button id="add-recipe-volume-target" variant="secondary" disabled={locked || !availablePurpose} onClick={() => {
          if (!availablePurpose) return;
          const key = newCreationId(); focusId.current = `recipe-volume-target-${key}`;
          setTargets((rows) => [...rows, { key, purpose: availablePurpose.value, amount: '', unit: 'L' }]);
        }}>Add volume target</Button>
      </div>

      <div className="recipe-actions">
        <Button type="submit" busy={busy && dirty} disabled={locked || !saved || !dirty || incomplete || conflict}>{busy ? 'Saving details…' : 'Save details'}</Button>
        {dirty && saved && <Button variant="secondary" disabled={locked} onClick={() => {
          setSource(saved.source ?? ''); setTags(saved.tags.map((tag) => ({ key: newCreationId(), value: tag })));
          setTargets(targetRows(saved.volume_targets)); setError(null); setNotice('Recipe detail changes discarded.');
        }}>Discard detail changes</Button>}
      </div>
      {incomplete && <p className="field-error" role="status">Complete or remove blank tags and volume target amounts before saving.</p>}
      <p className="muted small" aria-live="polite">{dirty ? 'Unsaved recipe detail changes' : 'Recipe details are saved only when you choose Save details.'}</p>
    </form>
  </Card>;
}
