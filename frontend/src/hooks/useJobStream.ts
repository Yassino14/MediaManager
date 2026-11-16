import { useEffect, useState } from 'react';
import type { JobRecord } from '../types';

export function useJobStream(onJobEvent: (event: string, job: JobRecord) => void) {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource('/api/events/stream');
    source.onopen = () => setConnected(true);
    source.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.event === 'connected') {
          setConnected(true);
        } else if (data.job) {
          onJobEvent(data.event, data.job as JobRecord);
        }
      } catch {
        // Ignore keep-alive comments
      }
    };
    source.onerror = () => {
      setConnected(false);
    };
    return () => {
      source.close();
    };
  }, [onJobEvent]);

  return { connected };
}
