// =============================================================================
// services/pathsService.ts — attack-paths REST surface
// =============================================================================

import type { GraphPayload } from '@/types/graph';
import type { AttackPathDetail, AttackPathSummary, TimelineStep } from '@/types/paths';
import { apiClient } from './apiClient';

export interface PathsListFilters {
  minConfidence?: number;
  since?: string;
  until?: string;
  page?: number;
}

function toParams(filters: PathsListFilters): Record<string, unknown> {
  return {
    min_confidence: filters.minConfidence,
    since: filters.since,
    until: filters.until,
    page: filters.page,
  };
}

export const pathsService = {
  async list(
    filters: PathsListFilters = {},
  ): Promise<{ rows: AttackPathSummary[]; total: number }> {
    return apiClient.get<{ rows: AttackPathSummary[]; total: number }>(
      '/paths',
      toParams(filters),
    );
  },
  async detail(pathId: string): Promise<AttackPathDetail> {
    return apiClient.get<AttackPathDetail>(`/paths/${encodeURIComponent(pathId)}`);
  },
  async timeline(pathId: string): Promise<TimelineStep[]> {
    return apiClient.get<TimelineStep[]>(`/paths/${encodeURIComponent(pathId)}/timeline`);
  },
  async graph(pathId: string): Promise<GraphPayload> {
    return apiClient.get<GraphPayload>(`/paths/${encodeURIComponent(pathId)}/graph`);
  },
};
