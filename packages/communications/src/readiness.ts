export type ServiceState = 'checking' | 'ready' | 'unavailable';

export async function checkReadiness(signal: AbortSignal): Promise<'ready' | 'unavailable'> {
  const response = await fetch('/api/v1/readiness', {
    signal: AbortSignal.any([signal, AbortSignal.timeout(5000)]),
    cache: 'no-store', headers: { Accept: 'application/json' },
  });
  const body: unknown = await response.json();
  if (!body || typeof body !== 'object' || !('status' in body)) return 'unavailable';
  return response.status === 200 && body.status === 'ready' ? 'ready' : 'unavailable';
}
