// =============================================================================
// services/baselineService.ts — rare-edge baseline learn/freeze control
// =============================================================================

import { apiClient } from './apiClient';

export type BaselineMode = 'learning' | 'frozen';

export interface BaselineStatus {
  mode: BaselineMode;
  learning: boolean;
  edge_count: number;
  is_dirty: boolean;
  baseline_path: string | null;
  saved?: string | null;
}

export const baselineService = {
  async status(): Promise<BaselineStatus> {
    return apiClient.get<BaselineStatus>('/baseline/status');
  },
  async setMode(mode: BaselineMode): Promise<BaselineStatus> {
    return apiClient.post<BaselineStatus>('/baseline/mode', { mode });
  },
  async reset(): Promise<BaselineStatus> {
    return apiClient.post<BaselineStatus>('/baseline/reset');
  },
};
