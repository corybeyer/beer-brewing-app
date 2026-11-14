import { useEffect, useRef, useState } from 'react';
import { Button, Card, SelectField, TextField } from '@brewery/ui';
import {
  applyConversion, createConversionPreview, listGrainProfiles, loadConversionPreview, loadIngredients, newCreationId,
  RecipeRequestError, type ConversionPreview, type GrainProfile, type RecipeIngredient,
} from '@brewery/communications/recipes';

type Props = { versionId: string; revision: number; disabled: boolean; onBusyChange: (busy: boolean) => void;
  onApplied: (revision: number) => void; onReviewLatest: () => void };
const issue = (error: unknown) => error instanceof RecipeRequestError ? error : new RecipeRequestError('unavailable', 'Conversion information is unavailable. Please retry.');
const decimal = (value: string) => /^[0-9]+(?:\.[0-9]{1,12})?$/.test(value);

export function ConversionPicker({ versionId, revision, disabled, onBusyChange, onApplied, onReviewLatest }: Props) {
  const [profiles, setProfiles] = useState<GrainProfile[]>([]);
  const [ingredients, setIngredients] = useState<RecipeIngredient[]>([]);
  const [sourceId, setSourceId] = useState(''); const [targetId, setTargetId] = useState('');
  const [sourcePotential, setSourcePotential] = useState(''); const [sourceRecovery, setSourceRecovery] = useState('');
  const [sourceProvenance, setSourceProvenance] = useState(''); const [targetPotential, setTargetPotential] = useState('');
  const [targetRecovery, setTargetRecovery] = useState(''); const [targetProvenance, setTargetProvenance] = useState('');
  const [point, setPoint] = useState(''); const [unit, setUnit] = useState('');
  const [preview, setPreview] = useState<ConversionPreview | null>(null);
  const [pendingProposalId, setPendingProposalId] = useState<string | null>(null);
  const [busy, setBusy] = useState(true); const [error, setError] = useState<RecipeRequestError | null>(null);
  const [notice, setNotice] = useState('');
  const [retry, setRetry] = useState(0);
  const activeRequest = useRef<AbortController | null>(null);
  const skipRevisionReload = useRef(false);

  useEffect(() => {
    if (skipRevisionReload.current) { skipRevisionReload.current = false; return; }
    const controller = new AbortController(); setBusy(true); setError(null);
    Promise.all([listGrainProfiles(controller.signal), loadIngredients(versionId, controller.signal)]).then(([grainProfiles, list]) => {
      if (controller.signal.aborted) return;
      setProfiles(grainProfiles); setIngredients(list.ingredients);
      setSourceId(list.ingredients.find((item) => ['grain', 'other'].includes(item.category ?? '') && item.quantity && item.unit)?.id ?? '');
      setTargetId(grainProfiles[0]?.revision_id ?? ''); setPreview(null);
    }).catch((failure: unknown) => { if (!controller.signal.aborted) setError(issue(failure)); })
      .finally(() => { if (!controller.signal.aborted) { setBusy(false); onBusyChange(false); } });
    return () => { controller.abort(); activeRequest.current?.abort(); onBusyChange(false); };
  }, [versionId, revision, retry]);

  useEffect(() => { const target = profiles.find((item) => item.revision_id === targetId); setTargetPotential(target?.potential_ppg ?? ''); }, [profiles, targetId]);
  const source = ingredients.find((item) => item.id === sourceId);
  const target = profiles.find((item) => item.revision_id === targetId);
  const valid = Boolean(source && source.quantity && source.unit && target && decimal(sourcePotential) && Number(sourcePotential) > 0 && decimal(sourceRecovery) &&
    Number(sourceRecovery) > 0 && Number(sourceRecovery) <= 1 && sourceProvenance.trim() && decimal(targetPotential) &&
    Number(targetPotential) > 0 && decimal(targetRecovery) && Number(targetRecovery) > 0 && Number(targetRecovery) <= 1 && targetProvenance.trim() && point && unit);

  async function propose() {
    if (!valid || disabled || !source || !target) return;
    setBusy(true); onBusyChange(true); setError(null); setNotice(''); setPreview(null);
    const controller = new AbortController(); activeRequest.current = controller;
    const proposalId = pendingProposalId ?? newCreationId(); setPendingProposalId(proposalId);
    try {
      const value = await createConversionPreview(versionId, { expected_revision: revision, proposal_id: proposalId,
        source_ingredient_id: source.id, target_revision_id: target.revision_id,
        source_potential_ppg: sourcePotential, source_recovery: sourceRecovery, source_provenance: sourceProvenance.trim(),
        target_potential_ppg: target.potential_ppg === null ? targetPotential : null, target_recovery: targetRecovery,
        target_provenance: targetProvenance.trim(), comparison_point: point, target_unit: unit }, controller.signal);
      setPreview(value);
      setPendingProposalId(value.proposal_id);
    } catch (failure) {
      try {
        const recovered = await loadConversionPreview(versionId, proposalId, controller.signal);
        setPreview(recovered); setPendingProposalId(recovered.proposal_id);
        setNotice('The saved preview was recovered after the request response was interrupted.');
      } catch { setError(issue(failure)); }
    }
    finally { setBusy(false); onBusyChange(false); }
  }
  async function apply() {
    if (!preview || disabled) return;
    setBusy(true); onBusyChange(true); setError(null); setNotice('');
    const controller = new AbortController(); activeRequest.current = controller;
    try {
      const value = await applyConversion(versionId, preview.proposal_id, revision, controller.signal);
      setIngredients((rows) => rows.map((row) => row.id === preview.source_ingredient_id ? {
        ...row, id: preview.target_ingredient_id, name: preview.target_name, category: 'grain',
        quantity: preview.target_amount, unit: preview.target_unit,
      } : row));
      skipRevisionReload.current = true;
      onApplied(value.edit_revision); setPreview(null); setPendingProposalId(null);
      setNotice('Conversion applied. Review the updated ingredient list.');
    } catch (failure) { setError(issue(failure)); }
    finally { setBusy(false); onBusyChange(false); }
  }

  return <Card className="content-card recipe-form" aria-label="Grain conversion picker" aria-busy={busy}>
    <h2>Explore a grain conversion</h2>
    <p className="muted">This estimates equal gravity contribution. It does not claim equal flavor or brewing behavior, or adapt mash instructions. Review your mash plan separately.</p>
    {busy && <p aria-live="polite">Loading conversion data or saving…</p>}
    {notice && <p role="status">{notice}</p>}
    {error && <div role="alert"><p>{error.message}</p>{error.issues.map((item, index) => <p key={index}>{item.path}: {item.message}</p>)}
      {error.code === 'conflict'
        ? <Button variant="secondary" disabled={disabled || busy} onClick={onReviewLatest}>Review latest recipe</Button>
        : <Button variant="secondary" disabled={disabled || busy} onClick={() => setRetry((attempt) => attempt + 1)}>Retry loading conversion data</Button>}</div>}
    {!busy && !error && profiles.length === 0 && <p>No sourced grain profiles are available. Add a grain profile to the catalogue before comparing conversions.</p>}
    {!busy && profiles.length > 0 && <>
      {ingredients.filter((item) => ['grain', 'other'].includes(item.category ?? '') && item.quantity && item.unit).length === 0
        ? <p>Add a saved grain or fermentable with a mass and unit before creating a conversion preview.</p>
        : <>
          <p className="muted small">Choose a saved grain or other fermentable. Do not select salts or non-fermentables.</p>
          <SelectField label="Saved source ingredient" value={sourceId} disabled={disabled || busy || Boolean(preview)} onChange={(event) => { setSourceId(event.target.value); setPreview(null); setPendingProposalId(null); }}>
            {ingredients.filter((item) => ['grain', 'other'].includes(item.category ?? '') && item.quantity && item.unit).map((item) =>
              <option key={item.id} value={item.id}>{item.name ?? 'Unnamed ingredient'} · {item.quantity} {item.unit}</option>)}
          </SelectField>
          <SelectField label="Sourced grain profile" value={targetId} disabled={disabled || busy || Boolean(preview)} onChange={(event) => { setTargetId(event.target.value); setPreview(null); setPendingProposalId(null); }}>
            {profiles.map((item) => <option key={item.revision_id} value={item.revision_id}>{item.name} · {item.manufacturer ?? item.source_label}</option>)}
          </SelectField>
          {target && <p className="muted small">Source: {target.source_url ? <a href={target.source_url} target="_blank" rel="noopener noreferrer">{target.source_label}</a> : target.source_label}, retrieved {new Date(target.source_retrieved_at).toLocaleDateString()} · {target.potential_status === 'unknown' ? 'Potential not recorded' : `potential ${targetPotential} PPG (${target.potential_status})`}{target.potential_note ? ` · ${target.potential_note}` : ''}{target.flavor_notes ? ` · ${target.flavor_notes}` : ''}</p>}
          <TextField label="Source potential (PPG)" inputMode="decimal" value={sourcePotential} disabled={disabled || busy || Boolean(preview)} onChange={(event) => { setSourcePotential(event.target.value); setPendingProposalId(null); }} hint="Enter the value and source you are using." />
          <TextField label="Source recovery fraction" inputMode="decimal" value={sourceRecovery} disabled={disabled || busy || Boolean(preview)} onChange={(event) => { setSourceRecovery(event.target.value); setPendingProposalId(null); }} hint="For example, 0.75. No default is assumed." />
          <TextField label="Source potential provenance" value={sourceProvenance} disabled={disabled || busy || Boolean(preview)} onChange={(event) => { setSourceProvenance(event.target.value); setPendingProposalId(null); }} />
          {target?.potential_ppg === null && <TextField label="Target potential (PPG)" inputMode="decimal" value={targetPotential} disabled={disabled || busy || Boolean(preview)} onChange={(event) => { setTargetPotential(event.target.value); setPendingProposalId(null); }} hint="This profile has no potential; supply an explicit assumption." />}
          <TextField label="Target recovery fraction" inputMode="decimal" value={targetRecovery} disabled={disabled || busy || Boolean(preview)} onChange={(event) => { setTargetRecovery(event.target.value); setPendingProposalId(null); }} hint="For example, 0.75. No default is assumed." />
          <TextField label="Target recovery provenance" value={targetProvenance} disabled={disabled || busy || Boolean(preview)} onChange={(event) => { setTargetProvenance(event.target.value); setPendingProposalId(null); }} />
          <SelectField label="Comparison point" value={point} disabled={disabled || busy || Boolean(preview)} onChange={(event) => { setPoint(event.target.value); setPendingProposalId(null); }}><option value="">Choose a point</option><option value="kettle">Kettle</option><option value="fermenter">Fermenter</option></SelectField>
          <SelectField label="Weighing unit" value={unit} disabled={disabled || busy || Boolean(preview)} onChange={(event) => { setUnit(event.target.value); setPendingProposalId(null); }}><option value="">Choose a mass unit</option>{['g', 'kg', 'oz', 'lb'].map((item) => <option key={item}>{item}</option>)}</SelectField>
          <Button disabled={!valid || disabled || busy || Boolean(preview)} busy={busy && !preview} onClick={() => void propose()}>Create conversion preview</Button>
        </>}
    </>}
    {preview && <Card className="content-card" aria-label="Conversion preview">
      <h3>Review this proposed change</h3><p><strong>{source?.name ?? 'Source ingredient'}</strong> · {source?.quantity} {source?.unit} → <strong>{preview.target_name}</strong> · {preview.target_amount} {preview.target_unit}</p>
      <p>Exact result: {preview.exact_amount_numerator}/{preview.exact_amount_denominator} {preview.target_unit}. Comparison point: {preview.comparison_point}.</p>
      <p>{preview.weighing_note}</p><p>Catalog record: {target?.source_label}; flavor similarity is not established.</p>
      <div className="recipe-actions"><Button busy={busy} disabled={busy || disabled} onClick={() => void apply()}>Apply this conversion</Button>
        <Button variant="secondary" disabled={busy || disabled} onClick={() => { setPreview(null); setPendingProposalId(null); }}>Revise assumptions</Button></div>
    </Card>}
  </Card>;
}
