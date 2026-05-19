// =============================================================================
// stores/alertsStore.ts — alerts state
// =============================================================================

import { create } from 'zustand';

import type { Alert, Severity } from '@/types/alerts';
import { alertsService } from '@/services/alertsService';

const EMPTY_COUNTS: Record<Severity, number> = {
  info: 0, low: 0, medium: 0, high: 0, critical: 0,
};

const SEVERITIES: Severity[] = ['info', 'low', 'medium', 'high', 'critical'];

function isSeverity(value: unknown): value is Severity {
  return typeof value === 'string' && (SEVERITIES as string[]).includes(value);
}

function recomputeCounts(rows: Alert[]): Record<Severity, number> {
  const counts: Record<Severity, number> = { ...EMPTY_COUNTS };
  for (const alert of rows) {
    if (alert.status === 'closed') continue;
    const sev = isSeverity(alert.severity) ? alert.severity : 'info';
    counts[sev] = (counts[sev] ?? 0) + 1;
  }
  return counts;
}

function upsertAlert(rows: Alert[], next: Alert): Alert[] {
  const index = rows.findIndex((row) => row.alert_id === next.alert_id);
  if (index === -1) return [next, ...rows].slice(0, 500);
  const copy = rows.slice();
  copy[index] = next;
  return copy;
}

export interface AlertsState {
  rows: Alert[];
  total: number;
  openCounts: Record<Severity, number>;
  selectedId: string | null;
  isLoading: boolean;
  error: string | null;
  hydrate: () => Promise<void>;
  appendNew: (alert: Alert) => void;
  update: (alert: Alert) => void;
  select: (alertId: string | null) => void;
}

export const useAlertsStore = create<AlertsState>((set, get) => ({
  rows: [],
  total: 0,
  openCounts: { ...EMPTY_COUNTS },
  selectedId: null,
  isLoading: false,
  error: null,

  hydrate: async () => {
    set({ isLoading: true, error: null });
    try {
      const { rows, total } = await alertsService.list({ page: 1 });
      set({
        rows,
        total,
        openCounts: recomputeCounts(rows),
        isLoading: false,
      });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'failed to load alerts',
      });
    }
  },

  appendNew: (alert) => {
    const rows = upsertAlert(get().rows, alert);
    set({ rows, openCounts: recomputeCounts(rows), total: rows.length });
  },

  update: (alert) => {
    const rows = upsertAlert(get().rows, alert);
    set({ rows, openCounts: recomputeCounts(rows) });
  },

  select: (alertId) => set({ selectedId: alertId }),
}));
