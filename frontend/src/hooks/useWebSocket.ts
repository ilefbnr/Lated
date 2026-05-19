// =============================================================================
// hooks/useWebSocket.ts — single app-wide WebSocket lifecycle
// =============================================================================

import { useEffect, useRef } from 'react';

import { getAuthToken } from '@/services/apiClient';
import { useUIStore } from '@/stores/uiStore';
import { WSClient, getWsUrl } from '@/websocket/wsClient';
import { dispatchFrame } from '@/websocket/wsHandlers';
import { WS_CHANNELS } from '@/websocket/wsEvents';

const ALL_CHANNELS = [
  WS_CHANNELS.ALERTS,
  WS_CHANNELS.GRAPH,
  WS_CHANNELS.HOSTS,
  WS_CHANNELS.FLOWS,
  WS_CHANNELS.TIMELINE,
];

export function useBootstrapWebSocket(): void {
  const clientRef = useRef<WSClient | null>(null);
  const setWsConnected = useUIStore((state) => state.setWsConnected);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (clientRef.current !== null) return;

    const client = new WSClient(getWsUrl(), getAuthToken());
    clientRef.current = client;

    const offOpen = client.onOpen(() => {
      setWsConnected(true);
      client.subscribe(ALL_CHANNELS);
    });
    const offClose = client.onClose(() => setWsConnected(false));
    const offMessage = client.onMessage(dispatchFrame);

    client.connect();

    return () => {
      offOpen();
      offClose();
      offMessage();
      client.close();
      clientRef.current = null;
      setWsConnected(false);
    };
  }, [setWsConnected]);
}
