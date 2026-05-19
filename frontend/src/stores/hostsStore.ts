// =============================================================================
// stores/hostsStore.ts — hosts + risk state
// =============================================================================

import { create } from 'zustand';

import type { Host, HostHeatmapCell, HostRiskPoint, HostRiskSummary } from '@/types/hosts';
import { hostsService } from '@/services/hostsService';

export interface HostsState {
  list: Host[];
  topRisky: HostRiskSummary[];
  profile: Host | null;
  riskEvolution: HostRiskPoint[];
  heatmap: HostHeatmapCell[];
  isLoading: boolean;
  error: string | null;
  hydrate: () => Promise<void>;
  selectHost: (hostId: string) => Promise<void>;
  applyRiskUpdate: (summary: HostRiskSummary) => void;
}

function mergeRisk(current: HostRiskSummary[], update: HostRiskSummary): HostRiskSummary[] {
  const index = current.findIndex((row) => row.host_id === update.host_id);
  if (index === -1) return [update, ...current];
  const copy = current.slice();
  copy[index] = update;
  return copy;
}

export const useHostsStore = create<HostsState>((set) => ({
  list: [],
  topRisky: [],
  profile: null,
  riskEvolution: [],
  heatmap: [],
  isLoading: false,
  error: null,

  hydrate: async () => {
    set({ isLoading: true, error: null });
    try {
      const [list, topRisky] = await Promise.all([
        hostsService.list(),
        hostsService.topRisky(),
      ]);
      set({ list, topRisky, isLoading: false });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'failed to load hosts',
      });
    }
  },

  selectHost: async (hostId) => {
    set({ isLoading: true, error: null });
    try {
      const [profile, riskEvolution, heatmap] = await Promise.all([
        hostsService.profile(hostId),
        hostsService.riskEvolution(hostId),
        hostsService.heatmap(hostId),
      ]);
      set({ profile, riskEvolution, heatmap, isLoading: false });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'failed to load host profile',
      });
    }
  },

  applyRiskUpdate: (summary) => {
    set((state) => ({ topRisky: mergeRisk(state.topRisky, summary) }));
  },
}));
