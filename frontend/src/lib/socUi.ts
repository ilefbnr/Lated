import type { DetectionKind, Severity } from '@/types/alerts';

export const MITRE_MAP: Record<string, { name: string; tactic: string }> = {
  T1021: { name: 'Remote Services', tactic: 'Lateral Movement' },
  'T1021.001': { name: 'RDP', tactic: 'Lateral Movement' },
  'T1021.004': { name: 'SSH', tactic: 'Lateral Movement' },
  T1570: { name: 'Lateral Tool Transfer', tactic: 'Lateral Movement' },
  T1047: { name: 'Windows Management Instrumentation', tactic: 'Execution' },
  T1046: { name: 'Network Service Discovery', tactic: 'Discovery' },
  T1087: { name: 'Account Discovery', tactic: 'Discovery' },
  T1078: { name: 'Valid Accounts', tactic: 'Defense Evasion' },
  'T1078.002': { name: 'Domain Accounts', tactic: 'Defense Evasion' },
};

export const TACTIC_COLORS: Record<string, string> = {
  Reconnaissance: '#60A5FA',
  Discovery: '#60A5FA',
  'Initial Access': '#34D399',
  Execution: '#FB923C',
  'Lateral Movement': '#F43F5E',
  'Defense Evasion': '#A78BFA',
  Collection: '#FBBF24',
  Exfiltration: '#F472B6',
  default: '#94A3B8',
};

const DEFAULT_TACTIC_COLOR = '#94A3B8';

export const SEVERITY_COLORS: Record<Severity, string> = {
  info: '#60A5FA',
  low: '#34D399',
  medium: '#FBBF24',
  high: '#FB923C',
  critical: '#F43F5E',
};

export const RECOMMENDATIONS: Record<DetectionKind, Array<{ action: string; priority: 'critical' | 'high' | 'medium' | 'low' }>> = {
  lateral_movement: [
    { action: 'Isolate the subject host from the network.', priority: 'critical' },
    { action: 'Rotate credentials likely used during the chain.', priority: 'high' },
    { action: 'Block SMB/RDP movement between implicated segments.', priority: 'high' },
  ],
  reconnaissance: [
    { action: 'Rate-limit or quarantine the scanning host.', priority: 'high' },
    { action: 'Review LDAP/Kerberos activity for enumerated identities.', priority: 'medium' },
    { action: 'Validate whether the host is expected on this segment.', priority: 'medium' },
  ],
  fusion: [
    { action: 'Correlate the fused signals with endpoint telemetry.', priority: 'high' },
    { action: 'Open an incident and preserve volatile evidence.', priority: 'medium' },
    { action: 'Escalate to supervisor review for disposition.', priority: 'medium' },
  ],
  correlation: [
    { action: 'Confirm the linked detections represent one incident.', priority: 'high' },
    { action: 'Review adjacent assets for follow-on movement.', priority: 'medium' },
    { action: 'Update detection thresholds if this is benign.', priority: 'low' },
  ],
};

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatShortTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function tacticColor(tactic?: string | null): string {
  if (!tactic) return DEFAULT_TACTIC_COLOR;
  return TACTIC_COLORS[tactic] ?? DEFAULT_TACTIC_COLOR;
}

export function detectionKindLabel(kind: string): string {
  return kind.replace(/_/g, ' ');
}

export function scoreColor(score: number): string {
  if (score >= 0.85) return SEVERITY_COLORS.critical;
  if (score >= 0.7) return SEVERITY_COLORS.high;
  if (score >= 0.5) return SEVERITY_COLORS.medium;
  return 'rgb(var(--lated-cyan) / 1)';
}
