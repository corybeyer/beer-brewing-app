export type MassUnit = 'g' | 'kg' | 'oz' | 'lb';
export type ComparisonPoint = 'kettle' | 'fermenter';
export interface ConversionYield {
  potential_ppg: string; recovery_fraction: string; comparison_point: ComparisonPoint; provenance: string;
}
export interface ConversionInput {
  source_mass: { amount: string; unit: MassUnit }; source_yield: ConversionYield;
  target_yield: ConversionYield; target_unit: MassUnit;
}
export interface ExactQuantity { numerator: string; denominator: string }
export interface ConversionResult {
  source_mass: ConversionInput['source_mass']; source_yield: ConversionYield; target_yield: ConversionYield;
  amount: ExactQuantity; unit: MassUnit; gravity_points_gallons: ExactQuantity;
  display_amount: string; display_decimal_places: 6; calculation_version: 'gravity-equivalence/v1';
}
export interface ConversionIssue { path: string; message: string }
export class ConversionRequestError extends Error {
  constructor(public code: string, message: string, public issues: ConversionIssue[] = []) { super(message); }
}
const object = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const unit = (value: unknown): value is MassUnit => typeof value === 'string' && ['g', 'kg', 'oz', 'lb'].includes(value);
const decimal = (value: unknown) => typeof value === 'string' && /^[0-9]+(?:\.[0-9]+)?$/.test(value) && value.length <= 80;
const fraction = (value: unknown) => object(value) && typeof value.numerator === 'string' && typeof value.denominator === 'string' &&
  /^[1-9][0-9]{0,511}$/.test(value.numerator) && /^[1-9][0-9]{0,511}$/.test(value.denominator);
const yieldValue = (value: unknown) => object(value) && decimal(value.potential_ppg) && decimal(value.recovery_fraction) &&
  (value.comparison_point === 'kettle' || value.comparison_point === 'fermenter') && typeof value.provenance === 'string' && value.provenance.length > 0;

export async function calculateConversion(input: ConversionInput, signal: AbortSignal): Promise<ConversionResult> {
  try {
    const response = await fetch('/api/v1/conversions/fermentable', { method: 'POST',
      signal: AbortSignal.any([signal, AbortSignal.timeout(5000)]), cache: 'no-store', credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify(input) });
    const value: unknown = await response.json();
    if (!response.ok) {
      if (object(value) && object(value.error) && typeof value.error.code === 'string' && typeof value.error.message === 'string') {
        const issues = Array.isArray(value.error.issues) ? value.error.issues.filter((issue): issue is ConversionIssue =>
          object(issue) && typeof issue.path === 'string' && typeof issue.message === 'string') : [];
        throw new ConversionRequestError(value.error.code, value.error.message, issues);
      }
      throw new ConversionRequestError('unavailable', 'The calculation could not be completed. Your entered values are still here. Please retry.');
    }
    if (response.status !== 200 || !object(value) || !object(value.source_mass) || !decimal(value.source_mass.amount) ||
        !unit(value.source_mass.unit) || value.source_mass.unit !== input.source_mass.unit || value.source_mass.amount !== input.source_mass.amount || !yieldValue(value.source_yield) || !yieldValue(value.target_yield) ||
        (value.source_yield as ConversionYield).comparison_point !== input.source_yield.comparison_point ||
        (value.target_yield as ConversionYield).comparison_point !== input.target_yield.comparison_point ||
        !['potential_ppg', 'recovery_fraction', 'comparison_point', 'provenance'].every((key) =>
          (value.source_yield as unknown as Record<string, unknown>)[key] === (input.source_yield as unknown as Record<string, unknown>)[key] &&
          (value.target_yield as unknown as Record<string, unknown>)[key] === (input.target_yield as unknown as Record<string, unknown>)[key]) ||
        !fraction(value.amount) || value.unit !== input.target_unit || !fraction(value.gravity_points_gallons) ||
        typeof value.display_amount !== 'string' || !(value.display_amount === '<0.000001' || /^[0-9]+\.[0-9]{6}$/.test(value.display_amount)) ||
        value.display_decimal_places !== 6 || value.calculation_version !== 'gravity-equivalence/v1') {
      throw new ConversionRequestError('invalid_response', 'The calculation response could not be read. Your entered values are still here. Please retry.');
    }
    return value as unknown as ConversionResult;
  } catch (error) {
    if (signal.aborted || error instanceof ConversionRequestError) throw error;
    throw new ConversionRequestError('unavailable', 'The calculation could not be completed. Your entered values are still here. Please retry.');
  }
}
