import { useCallback, useEffect, useRef, useState } from 'react';
import { checkReadiness, type ServiceState } from '@brewery/communications';

export function useService() {
  const [state, setState] = useState<ServiceState>('checking');
  const controller = useRef<AbortController | null>(null);
  const retry = useCallback(() => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setState('checking');
    void checkReadiness(current.signal).then(
      (result) => { if (!current.signal.aborted) setState(result); },
      () => { if (!current.signal.aborted) setState('unavailable'); },
    );
  }, []);

  useEffect(() => {
    retry();
    const refresh = () => retry();
    const visibility = () => { if (document.visibilityState === 'visible') retry(); };
    const interval = window.setInterval(retry, 30000);
    window.addEventListener('online', refresh);
    window.addEventListener('offline', refresh);
    document.addEventListener('visibilitychange', visibility);
    return () => {
      controller.current?.abort();
      window.clearInterval(interval);
      window.removeEventListener('online', refresh);
      window.removeEventListener('offline', refresh);
      document.removeEventListener('visibilitychange', visibility);
    };
  }, [retry]);
  return { state, retry };
}
