// =============================================================================
// types/paths.ts — AttackPath + timeline shapes (mirror of backend)
// =============================================================================

import type { Alert } from '@/types/alerts';

export interface AttackPathSummary {
  path_id: string;
  created_at: string;
  hosts: string[];
  pivot_hosts: string[];
  path_confidence: number;
  mitre_tactic_chain: string[];
  alert_count: number;
  schema_version: string;
}

export interface AttackPathDetail extends AttackPathSummary {
  timeline: Alert[];
}

export interface TimelineStep {
  step: number;
  ts: string;
  kind: string;
  subject_host: string;
  target_hosts: string[];
  evidence_alert_ids: string[];
  mitre_tags: string[];
}
