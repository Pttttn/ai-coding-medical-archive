import { useCallback, useEffect, useRef, useState } from 'react';
import { api, message } from './api';

export function useApi<T>(path: string, pollMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const lastPath = useRef(path);
  const reload = useCallback(() => setRevision(value => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    if (lastPath.current !== path) { setData(null); lastPath.current = path; }
    setLoading(true);
    async function read() {
      try {
        const result = await api<T>(path, { signal: controller.signal });
        if (!controller.signal.aborted) { setData(result); setError(''); }
      } catch (cause) { if (!controller.signal.aborted) setError(message(cause)); }
      finally {
        if (!controller.signal.aborted) {
          setLoading(false);
          if (pollMs > 0) timer = setTimeout(read, pollMs);
        }
      }
    }
    void read();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [path, revision, pollMs]);
  return { data, error, loading, reload, setData };
}

export function useDebounce<T>(value: T, delay = 350) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => { const timer = setTimeout(() => setDebounced(value), delay); return () => clearTimeout(timer); }, [value, delay]);
  return debounced;
}
