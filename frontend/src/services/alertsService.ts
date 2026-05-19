// =============================================================================
// services/alertsService.ts — alert REST surface
// =============================================================================

import type { Alert, Severity } from '@/types/alerts';
import { apiClient } from './apiClient';

export interface AlertsListFilters {
  severity?: Severity[];
  host?: string;
  since?: string;
  until?: string;
  page?: number;
}

function toParams(filters: AlertsListFilters): Record<string, unknown> {
  return {
    severity: filters.severity,
    host: filters.host,
    since: filters.since,
    until: filters.until,
    page: filters.page,
  };
}

const SEVERITIES: Severity[] = ['info', 'low', 'medium', 'high', 'critical'];

export const alertsService = {
  async list(filters: AlertsListFilters = {}): Promise<{ rows: Alert[]; total: number }> {
    return apiClient.get<{ rows: Alert[]; total: number }>('/alerts', toParams(filters));
  },
  async detail(alertId: string): Promise<Alert> {
    return apiClient.get<Alert>(`/alerts/${encodeURIComponent(alertId)}`);
  },
  async ack(alertId: string): Promise<Alert> {
    return apiClient.post<Alert>(`/alerts/${encodeURIComponent(alertId)}/ack`);
  },
  async close(alertId: string, disposition: string): Promise<Alert> {
    return apiClient.post<Alert>(`/alerts/${encodeURIComponent(alertId)}/close`, { disposition });
  },
  async summary(): Promise<Record<Severity, number>> {
    const { rows } = await this.list({ page: 1 });
    const counts: Record<Severity, number> = {
      info: 0, low: 0, medium: 0, high: 0, critical: 0,
    };
    for (const alert of rows) {
      if (alert.status === 'closed') continue;
      const sev = SEVERITIES.includes(alert.severity) ? alert.severity : 'info';
      counts[sev] = (counts[sev] ?? 0) + 1;
    }
    return counts;
  },
};
