// =============================================================================
// services/adminService.ts — admin-only REST surface
// =============================================================================

import { apiClient } from './apiClient';

export const adminService = {
  async reloadThresholds(): Promise<{ status: string }> {
    return apiClient.post<{ status: string }>('/admin/reload-thresholds');
  },
  async modelInfo(): Promise<Record<string, unknown>> {
    return apiClient.get<Record<string, unknown>>('/admin/model/info');
  },
};
