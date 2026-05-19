// =============================================================================
// services/discoveryService.ts — passive discovery bootstrap surface
// =============================================================================

import { apiClient } from './apiClient';

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
};
