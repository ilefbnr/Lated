// =============================================================================
// types/hosts.ts — Host + risk types
// =============================================================================
// Mirror of backend Host + risk shapes.
// =============================================================================

export interface Host {
  host_id: string;
  ip_addresses: string[];
  hostname: string | null;
  subnet: string | null;
  first_seen: string;
  last_seen: string;
  os_guess: string | null;
}

export interface HostRiskPoint {
  ts: string;
  risk: number; // 0..1
}

export interface HostRiskSummary {
  host_id: string;
  hostname: string | null;
  subnet: string | null;
  current_risk: number;
  last_alert_at: string | null;
  active_alerts: number;
}

export interface HostHeatmapCell {
  neighbor_host_id: string;
  intensity: number; // 0..1 normalized
  bytes: number;
  packets: number;
}
