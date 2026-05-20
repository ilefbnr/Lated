// =============================================================================
// services/discoveryService.ts — passive discovery bootstrap surface
// =============================================================================

import type { DiscoveryRunResult, DiscoveryUploadResult } from '@/types/discovery';
import { apiClient, getApiBaseUrl, getAuthToken, ApiError } from './apiClient';

export interface DiscoveryBootstrapResult {
  status: string;
  source_path: string;
  baseline_path: string;
  registry_path: string;
  generated_at: string;
  host_count: number;
  edge_count: number;
  subnet_count: number;
  gateway_count: number;
  service_count: number;
}

export const discoveryService = {
  async bootstrap(): Promise<DiscoveryBootstrapResult> {
    return apiClient.post<DiscoveryBootstrapResult>('/discovery/bootstrap');
  },
  async history(): Promise<DiscoveryRunResult[]> {
    return apiClient.get<DiscoveryRunResult[]>('/discovery/history');
  },
  async status(): Promise<{ latest: DiscoveryRunResult | null }> {
    return apiClient.get<{ latest: DiscoveryRunResult | null }>('/discovery/status');
  },
  async run(sourceKind: string, sourceValue: string, mode = 'passive'): Promise<DiscoveryRunResult> {
    return apiClient.post<DiscoveryRunResult>('/discovery/run', {
      source_kind: sourceKind,
      source_value: sourceValue,
      mode,
    });
  },
  async upload(file: File): Promise<DiscoveryUploadResult> {
    const form = new FormData();
    form.append('file', file);
    const response = await fetch(`${getApiBaseUrl()}/discovery/upload`, {
      method: 'POST',
      headers: getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : undefined,
      body: form,
    });
    if (!response.ok) {
      throw new ApiError(response.status, `HTTP_${response.status}`, response.statusText);
    }
    return await response.json() as DiscoveryUploadResult;
  },
};
