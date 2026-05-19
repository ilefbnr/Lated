// =============================================================================
// websocket/wsEvents.ts — event + channel constants (mirror of backend)
// =============================================================================
// Must stay in sync with backend's lated.common.constants. Centralizing the
// names here prevents typos when wiring handlers.
// =============================================================================

export const WS_CHANNELS = {
  ALERTS:   'alerts',
  GRAPH:    'graph',
  HOSTS:    'hosts',
  FLOWS:    'flows',
  HEALTH:   'health',
  TIMELINE: 'timeline',
} as const;

export const WS_EVENTS = {
  ALERT_NEW:        'alert.new',
  ALERT_UPDATE:     'alert.update',
  GRAPH_UPDATE:     'graph.update',
  HOST_RISK:        'host.risk',
  FLOW_NEW:         'flow.new',
  PATH_NEW:         'path.new',
  HEALTH_HEARTBEAT: 'health.heartbeat',
} as const;

export type WSChannel = typeof WS_CHANNELS[keyof typeof WS_CHANNELS];
export type WSEventName = typeof WS_EVENTS[keyof typeof WS_EVENTS];

export interface WSFrame<P = unknown> {
  channel: WSChannel;
  event: WSEventName;
  payload: P;
  ts: string;
}
