// =============================================================================
// websocket/wsClient.ts — WebSocket transport
// =============================================================================
//
// Wraps a single connection lifecycle with:
//   - bearer token via ?token=... query string (browsers cannot set headers),
//   - exponential backoff reconnect (250ms -> 5s, capped),
//   - send(channel,type,payload) helper for subscribe/unsubscribe,
//   - typed on/off for 'message' / 'open' / 'close' events.
// =============================================================================

import type { WSFrame } from './wsEvents';

type MessageHandler = (frame: WSFrame) => void;
type ConnectionHandler = () => void;

const RECONNECT_INITIAL_MS = 250;
const RECONNECT_MAX_MS = 5000;

export class WSClient {
  private socket: WebSocket | null = null;
  private url: string;
  private token: string | null;
  private closed = false;
  private reconnectAttempts = 0;
  private messageHandlers = new Set<MessageHandler>();
  private openHandlers = new Set<ConnectionHandler>();
  private closeHandlers = new Set<ConnectionHandler>();

  constructor(url: string, token: string | null) {
    this.url = url;
    this.token = token;
  }

  connect(): void {
    if (this.socket !== null) return;
    this.closed = false;
    const full = this.buildUrl();
    let socket: WebSocket;
    try {
      socket = new WebSocket(full);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;
    socket.onopen = () => {
      this.reconnectAttempts = 0;
      for (const handler of this.openHandlers) handler();
    };
    socket.onmessage = (event) => this.handleMessage(event);
    socket.onclose = () => {
      this.socket = null;
      for (const handler of this.closeHandlers) handler();
      if (!this.closed) this.scheduleReconnect();
    };
    socket.onerror = () => {
      try { socket.close(); } catch { /* ignore */ }
    };
  }

  close(): void {
    this.closed = true;
    if (this.socket !== null) {
      try { this.socket.close(); } catch { /* ignore */ }
      this.socket = null;
    }
  }

  send(channel: string, type: 'subscribe' | 'unsubscribe' | 'pong', payload?: unknown): void {
    const socket = this.socket;
    if (socket === null || socket.readyState !== WebSocket.OPEN) return;
    const frame: Record<string, unknown> = { type, channel };
    if (payload !== undefined) frame.payload = payload;
    try { socket.send(JSON.stringify(frame)); } catch { /* ignore */ }
  }

  subscribe(channels: string[]): void {
    for (const channel of channels) this.send(channel, 'subscribe');
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  onOpen(handler: ConnectionHandler): () => void {
    this.openHandlers.add(handler);
    return () => this.openHandlers.delete(handler);
  }

  onClose(handler: ConnectionHandler): () => void {
    this.closeHandlers.add(handler);
    return () => this.closeHandlers.delete(handler);
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data as string) as WSFrame;
      for (const handler of this.messageHandlers) handler(data);
    } catch {
      // ignore non-JSON frames silently — forward-compat
    }
  }

  private buildUrl(): string {
    if (!this.token) return this.url;
    const sep = this.url.includes('?') ? '&' : '?';
    return `${this.url}${sep}token=${encodeURIComponent(this.token)}`;
  }

  private scheduleReconnect(): void {
    if (this.closed) return;
    const delay = Math.min(
      RECONNECT_MAX_MS,
      RECONNECT_INITIAL_MS * 2 ** Math.min(this.reconnectAttempts, 5),
    );
    this.reconnectAttempts += 1;
    setTimeout(() => {
      if (!this.closed) this.connect();
    }, delay);
  }
}

const DEFAULT_WS_URL = 'ws://localhost:8000/ws';

export function getWsUrl(): string {
  const url = process.env.NEXT_PUBLIC_WS_URL;
  if (typeof url === 'string' && url.length > 0) return url;
  return DEFAULT_WS_URL;
}
