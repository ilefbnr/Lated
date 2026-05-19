// =============================================================================
// services/flowsService.ts — flows REST surface
// =============================================================================

import type { SuspiciousFlow } from '@/types/flows';
import { apiClient } from './apiClient';

export interface FlowsFilters {
  q?: string;
  minSuspicion?: number;
  since?: string;
  until?: string;
  sort?: 'ts' | 'bytes' | 'packets' | 'suspicion';
  page?: number;
}

function toParams(filters: FlowsFilters): Record<string, unknown> {
  return {
    q: filters.q,
    min_suspicion: filters.minSuspicion,
    since: filters.since,
    until: filters.until,
    sort: filters.sort,
    page: filters.page,
  };
}

export const flowsService = {
  async list(filters: FlowsFilters = {}): Promise<{ rows: SuspiciousFlow[]; total: number }> {
    return apiClient.get<{ rows: SuspiciousFlow[]; total: number }>('/flows', toParams(filters));
  },
  async detail(flowId: string): Promise<SuspiciousFlow> {
    return apiClient.get<SuspiciousFlow>(`/flows/${encodeURIComponent(flowId)}`);
  },
  async byHost(hostId: string): Promise<SuspiciousFlow[]> {
    return apiClient.get<SuspiciousFlow[]>(`/flows/by-host/${encodeURIComponent(hostId)}`);
  },
};
