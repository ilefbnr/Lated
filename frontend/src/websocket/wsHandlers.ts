// =============================================================================
// websocket/wsHandlers.ts — incoming-event router
// =============================================================================

import { WS_EVENTS, type WSFrame } from './wsEvents';
import type { Alert } from '@/types/alerts';
import type { SuspiciousFlow } from '@/types/flows';
import type { GraphPayload } from '@/types/graph';
import type { HostRiskSummary } from '@/types/hosts';

import { useAlertsStore } from '@/stores/alertsStore';
import { useFlowsStore } from '@/stores/flowsStore';
import { useGraphStore } from '@/stores/graphStore';
import { useHostsStore } from '@/stores/hostsStore';
import { useUIStore } from '@/stores/uiStore';

export function dispatchFrame(frame: WSFrame): void {
  switch (frame.event) {
    case WS_EVENTS.ALERT_NEW:
      useAlertsStore.getState().appendNew(frame.payload as Alert);
      break;
    case WS_EVENTS.ALERT_UPDATE:
      useAlertsStore.getState().update(frame.payload as Alert);
      break;
    case WS_EVENTS.GRAPH_UPDATE:
      useGraphStore.getState().applyDelta(frame.payload as GraphPayload);
      break;
    case WS_EVENTS.HOST_RISK:
      useHostsStore.getState().applyRiskUpdate(frame.payload as HostRiskSummary);
      break;
    case WS_EVENTS.FLOW_NEW:
      useFlowsStore.getState().enqueue(frame.payload as SuspiciousFlow);
      break;
    case WS_EVENTS.PATH_NEW:
      // path.new payload also carries an embedded graph subview when emitted
      // by the alert engine — apply it as a delta so the canvas can reflect.
      if (frame.payload && typeof frame.payload === 'object') {
        const maybeGraph = (frame.payload as { graph?: GraphPayload }).graph;
        if (maybeGraph && Array.isArray(maybeGraph.nodes) && Array.isArray(maybeGraph.edges)) {
          useGraphStore.getState().applyDelta(maybeGraph);
        }
      }
      break;
    case WS_EVENTS.HEALTH_HEARTBEAT:
      useUIStore.getState().setWsConnected(true);
      break;
    default:
      // unknown event — forward-compatible
      break;
  }
}
