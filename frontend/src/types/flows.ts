// =============================================================================
// types/flows.ts — Suspicious-flows table types
// =============================================================================

export type FlowProtocol = 'tcp' | 'udp' | 'icmp' | 'other';

export interface SuspiciousFlow {
  flow_id: string;
  ts: string;
  src_host: string;
  dst_host: string;
  src_port: number;
  dst_port: number;
  protocol: FlowProtocol;
  duration: number;
  packet_count: number;
  byte_count: number;
  suspicion: number;     // 0..1
  related_alert_id?: string;
}
