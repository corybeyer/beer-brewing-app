import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Badge, Button, Card, InlineNote, PageHeading, SelectField, TextField } from '@brewery/ui';
import { calculateConversion, ConversionRequestError, type ComparisonPoint, type ConversionInput, type ConversionIssue, type ConversionResult, type MassUnit } from '@brewery/communications/conversions';
import './ConversionCalculator.css';

interface Inputs {
  amount: string; sourceUnit: MassUnit; sourcePotential: string; sourceRecovery: string; sourceProvenance: string;
  targetUnit: MassUnit; targetPotential: string; targetRecovery: string; targetProvenance: string; comparisonPoint: ComparisonPoint | '';
}
const blank: Inputs = { amount: '', sourceUnit: 'lb', sourcePotential: '', sourceRecovery: '', sourceProvenance: '',
  targetUnit: 'lb', targetPotential: '', targetRecovery: '', targetProvenance: '', comparisonPoint: '' };
const example: Inputs = { amount: '3', sourceUnit: 'lb', sourcePotential: '45', sourceRecovery: '1',
  sourceProvenance: 'Illustrative DME benchmark at 45 PPG; full kettle recovery assumed.', targetUnit: 'lb', targetPotential: '37',
  targetRecovery: '0.75', targetProvenance: 'Illustrative grain benchmark at 37 PPG; mash recovery assumed at 0.75.', comparisonPoint: 'kettle' };
const units: MassUnit[] = ['g', 'kg', 'oz', 'lb'];

export function ConversionCalculator() {
  const [inputs, setInputs] = useState<Inputs>(blank);
  const [result, setResult] = useState<ConversionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [issues, setIssues] = useState<ConversionIssue[]>([]);
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  useEffect(() => () => { generation.current += 1; request.current?.abort(); }, []);

  function clearCalculation() {
    generation.current += 1; request.current?.abort(); request.current = null;
    setBusy(false); setResult(null); setError(null); setIssues([]);
  }
  function update<K extends keyof Inputs>(key: K, value: Inputs[K]) { clearCalculation(); setInputs((current) => ({ ...current, [key]: value })); }
  function fieldError(path: string) { return issues.find((issue) => issue.path === path)?.message; }
  async function calculate(event: FormEvent) {
    event.preventDefault(); clearCalculation();
    if (!inputs.comparisonPoint) {
      setError('Choose the comparison point for both yield assumptions.');
      setIssues([{ path: 'comparison_point', message: 'Choose kettle or fermenter.' }]); return;
    }
    const payload: ConversionInput = { source_mass: { amount: inputs.amount, unit: inputs.sourceUnit },
      source_yield: { potential_ppg: inputs.sourcePotential, recovery_fraction: inputs.sourceRecovery,
        comparison_point: inputs.comparisonPoint, provenance: inputs.sourceProvenance },
      target_yield: { potential_ppg: inputs.targetPotential, recovery_fraction: inputs.targetRecovery,
        comparison_point: inputs.comparisonPoint, provenance: inputs.targetProvenance }, target_unit: inputs.targetUnit };
    const controller = new AbortController(); request.current = controller;
    const id = ++generation.current; setBusy(true);
    try { const response = await calculateConversion(payload, controller.signal); if (generation.current === id) setResult(response); }
    catch (failure) { if (generation.current === id && !controller.signal.aborted) {
      const problem = failure instanceof ConversionRequestError ? failure : new ConversionRequestError('unavailable', 'Calculation unavailable. Please retry.');
      setError(problem.message); setIssues(problem.issues);
    } } finally { if (generation.current === id) { setBusy(false); request.current = null; } }
  }
  const comparisonError = fieldError('comparison_point') ?? fieldError('source_yield.comparison_point') ?? fieldError('target_yield.comparison_point');
  return <>
    <PageHeading eyebrow="Brewing calculators" title="Grain & extract conversion" description="Compare ingredient masses using explicit potential and recovery assumptions." />
    <div className="calculator-layout">
      <Card className="content-card"><form className="calculator-form" onSubmit={calculate} noValidate aria-label="Fermentable conversion">
        <div className="calculator-actions"><Button variant="secondary" onClick={() => { clearCalculation(); setInputs(example); }}>Load illustrative example</Button></div>
        <p className="small muted">The example uses assumed DME and grain potentials. It is a calculation benchmark, not manufacturer data or a recipe recommendation.</p>
        <div className="calculator-field"><p><strong>Comparison point for both sides</strong></p>
          <SelectField label="Comparison point for both sides" value={inputs.comparisonPoint} aria-invalid={Boolean(comparisonError)} aria-describedby={comparisonError ? 'conversion-comparison-hint conversion-comparison-error' : 'conversion-comparison-hint'} onChange={(event) => update('comparisonPoint', event.target.value as Inputs['comparisonPoint'])}>
            <option value="">Choose a comparison point</option><option value="kettle">Kettle</option><option value="fermenter">Fermenter</option>
          </SelectField><p id="conversion-comparison-hint" className="field-hint">Use recoveries measured or assumed at the same point. Recovery 1 means no losses through that point.</p>
          {comparisonError && <p className="field-error" id="conversion-comparison-error">{comparisonError}</p>}
        </div>
        <div className="calculator-columns">
          <section className="calculator-form" aria-labelledby="conversion-source-heading"><h2 id="conversion-source-heading">Original ingredient</h2>
            <TextField label="Source amount" inputMode="decimal" value={inputs.amount} maxLength={80} error={fieldError('source_mass.amount')} onChange={(event) => update('amount', event.target.value)} />
            <div className="calculator-field"><p><strong>Source mass unit</strong></p><SelectField label="Source mass unit" value={inputs.sourceUnit} onChange={(event) => update('sourceUnit', event.target.value as MassUnit)}>{units.map((unit) => <option key={unit}>{unit}</option>)}</SelectField></div>
            <TextField label="Source potential (PPG)" inputMode="decimal" value={inputs.sourcePotential} maxLength={80} hint="Points per pound per US gallon, on an as-supplied mass basis." error={fieldError('source_yield.potential_ppg')} onChange={(event) => update('sourcePotential', event.target.value)} />
            <TextField label="Source recovery fraction" inputMode="decimal" value={inputs.sourceRecovery} maxLength={80} hint="Above 0 through 1. Supply the recovery assumption explicitly." error={fieldError('source_yield.recovery_fraction')} onChange={(event) => update('sourceRecovery', event.target.value)} />
            <TextField label="Source yield provenance" value={inputs.sourceProvenance} maxLength={1000} hint="Identify the product source and the recovery measurement or assumption." error={fieldError('source_yield.provenance')} onChange={(event) => update('sourceProvenance', event.target.value)} />
          </section>
          <section className="calculator-form" aria-labelledby="conversion-target-heading"><h2 id="conversion-target-heading">Replacement ingredient</h2>
            <div className="calculator-field"><p><strong>Target mass unit</strong></p><SelectField label="Target mass unit" value={inputs.targetUnit} onChange={(event) => update('targetUnit', event.target.value as MassUnit)}>{units.map((unit) => <option key={unit}>{unit}</option>)}</SelectField></div>
            <TextField label="Target potential (PPG)" inputMode="decimal" value={inputs.targetPotential} maxLength={80} hint="Use the replacement ingredient’s stated potential or an explicit assumption." error={fieldError('target_yield.potential_ppg')} onChange={(event) => update('targetPotential', event.target.value)} />
            <TextField label="Target recovery fraction" inputMode="decimal" value={inputs.targetRecovery} maxLength={80} hint="Above 0 through 1, at the same comparison point as the source." error={fieldError('target_yield.recovery_fraction')} onChange={(event) => update('targetRecovery', event.target.value)} />
            <TextField label="Target yield provenance" value={inputs.targetProvenance} maxLength={1000} hint="Identify the replacement product source and recovery assumption." error={fieldError('target_yield.provenance')} onChange={(event) => update('targetProvenance', event.target.value)} />
          </section>
        </div>
        {error && <div role="alert"><p>{error}</p>{issues.length > 0 && <ul>{issues.map((issue, index) => <li key={`${issue.path}-${index}`}>{issue.path}: {issue.message}</li>)}</ul>}</div>}
        <div className="calculator-actions"><Button type="submit" busy={busy}>{busy ? 'Calculating…' : 'Calculate conversion'}</Button></div>
        <p role="status" className="small muted">{busy ? 'Calculating with your current assumptions…' : result ? 'Calculation complete. Review the result and its assumptions below.' : 'Enter your assumptions, then calculate. No recipe changes are saved.'}</p>
      </form></Card>
      <div className="calculator-result">
        {result && <Card className="content-card" aria-label="Conversion result"><Badge tone="positive">Estimated gravity equivalence</Badge><h2>Rounded target mass</h2>
          <output aria-label="Target mass">{result.display_amount} {result.unit}</output>
          <p className="small muted">Rounded to {result.display_decimal_places} decimal places for display. Exact result: {result.amount.numerator}/{result.amount.denominator} {result.unit}.</p>
          <dl className="definition-list"><div><dt>Comparison point</dt><dd>{result.source_yield.comparison_point}</dd></div>
            <div><dt>Original assumptions</dt><dd>{result.source_yield.provenance}</dd></div><div><dt>Replacement assumptions</dt><dd>{result.target_yield.provenance}</dd></div>
            <div><dt>Calculation version</dt><dd>{result.calculation_version}</dd></div></dl>
        </Card>}
        <InlineNote icon="flask">Equivalent estimated gravity assumes the same wort volume. Review mash, boil, and hop-balance differences before adapting a recipe. This does not establish flavor equivalence, mash feasibility, or brewing readiness.</InlineNote>
      </div>
    </div>
  </>;
}
