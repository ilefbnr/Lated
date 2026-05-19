// =============================================================================
// types/alerts.ts — Alert + Severity types (mirror of backend schemas)
// =============================================================================
//
// PURPOSE
// -------
// TypeScript counterparts of the backend Pydantic models in
// `lated.common.schemas`. Hand-maintained in sync.
//
// WHY MIRROR INSTEAD OF GENERATING
// --------------------------------
// A generator would couple the frontend to the backend's exact codegen
// pipeline. Mirroring lets the SOC frontend stay deployable independently
// during partial outages, at the cost of disciplined updates when the
// schema changes.
// =============================================================================

export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical';
export type DetectionKind =
  | 'lateral_movement'
  | 'reconnaissance'
  | 'fusion'
  | 'correlation';

export interface AlertExplainability {
  lm?:      { score: number; top_contributing_edges: [string, string, number][] };
  recon?:   { score: number; triggered_signals: string[]; unique_destinations: number; unique_dst_ports: number };
  history?: { decayed_risk: number; last_alert_age_seconds: number | null };
  narrative?: string;
}

export interface Alert {
  alert_id: string;
  created_at: string;          // ISO-8601 UTC
  severity: Severity;
  kind: DetectionKind;
  subject_host: string;
  description: string;
  score: number;               // 0..1
  evidence: string[];          // canonical flow ids / snapshot ids
  mitre_tags: string[];
  explainability: AlertExplainability;
  status?: 'open' | 'ack' | 'closed';
}
