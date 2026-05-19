// =============================================================================
// services/hostsService.ts — host REST surface
// =============================================================================

import type { Host, HostRiskSummary, HostRiskPoint, HostHeatmapCell } from '@/types/hosts';
import { apiClient } from './apiClient';

export const hostsService = {
  async list(subnet?: string): Promise<Host[]> {
    return apiClient.get<Host[]>('/hosts', subnet ? { subnet } : undefined);
  },
  async topRisky(limit = 25): Promise<HostRiskSummary[]> {
    return apiClient.get<HostRiskSummary[]>('/hosts/top-risky', { limit });
  },
  async profile(hostId: string): Promise<Host> {
    return apiClient.get<Host>(`/hosts/${encodeURIComponent(hostId)}`);
  },
  async riskEvolution(hostId: string, hours = 24): Promise<HostRiskPoint[]> {
    return apiClient.get<HostRiskPoint[]>(
      `/hosts/${encodeURIComponent(hostId)}/risk-evolution`,
      { hours },
    );
  },
  async heatmap(hostId: string, windowMinutes = 60): Promise<HostHeatmapCell[]> {
    return apiClient.get<HostHeatmapCell[]>(
      `/hosts/${encodeURIComponent(hostId)}/heatmap`,
      { window_minutes: windowMinutes },
    );
  },
};
