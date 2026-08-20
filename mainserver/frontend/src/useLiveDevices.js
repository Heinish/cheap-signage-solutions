import { useEffect, useRef, useState } from 'react';
import { api } from './api';

/** Polls the device list, and refreshes immediately whenever the mainserver
 * pushes a status/online/offline event over /ws/ui. Polling stays as the
 * baseline so the UI is never more than a few seconds stale even if the
 * socket briefly drops. */
export function useLiveDevices() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const wsRef = useRef(null);

  const refresh = async () => {
    try {
      const data = await api.listDevices();
      setDevices(data);
    } catch {
      /* keep last known list on transient failure */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const poll = setInterval(refresh, 10000);

    let cancelled = false;
    const connect = () => {
      if (cancelled) return;
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${window.location.host}/ws/ui`);
      wsRef.current = ws;
      ws.onmessage = () => refresh();
      ws.onclose = () => {
        if (!cancelled) setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    };
    connect();

    return () => {
      cancelled = true;
      clearInterval(poll);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { devices, loading, refresh };
}
