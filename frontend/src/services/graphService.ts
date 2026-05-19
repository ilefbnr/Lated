// =============================================================================
// services/graphService.ts — graph REST surface
// =============================================================================

import type { GraphPayload } from '@/types/graph';
import { apiClient } from './apiClient';

export const graphService = {
  async baseline(): Promise<GraphPayload> {
    return apiClient.get<GraphPayload>('/graph/baseline');
  },
  async latest(): Promise<GraphPayload> {
    return apiClient.get<GraphPayload>('/graph/snapshot/latest');
  },
  async at(ts: string): Promise<GraphPayload> {
    return apiClient.get<GraphPayload>(`/graph/snapshot/${encodeURIComponent(ts)}`);
  },
  async hostEgo(hostId: string, hops = 1): Promise<GraphPayload> {
    return apiClient.get<GraphPayload>(
      `/graph/host/${encodeURIComponent(hostId)}`,
      { hops },
    );
  },
};
