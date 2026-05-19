// =============================================================================
// hooks/useHostRisk.ts — host risk binding
// =============================================================================

import { useEffect } from 'react';

import type { Host, HostHeatmapCell, HostRiskPoint, HostRiskSummary } from '@/types/hosts';
import { useHostsStore } from '@/stores/hostsStore';

export interface UseHostRisk {
  list: Host[];
  topRisky: HostRiskSummary[];
  profile: Host | null;
  riskEvolution: HostRiskPoint[];
  heatmap: HostHeatmapCell[];
  isLoading: boolean;
  error: string | null;
  selectHost: (hostId: string) => Promise<void>;
}

export function useHostRisk(): UseHostRisk {
  const list = useHostsStore((state) => state.list);
  const topRisky = useHostsStore((state) => state.topRisky);
  const profile = useHostsStore((state) => state.profile);
  const riskEvolution = useHostsStore((state) => state.riskEvolution);
  const heatmap = useHostsStore((state) => state.heatmap);
  const isLoading = useHostsStore((state) => state.isLoading);
  const error = useHostsStore((state) => state.error);
  const hydrate = useHostsStore((state) => state.hydrate);
  const selectHost = useHostsStore((state) => state.selectHost);

  useEffect(() => {
    if (topRisky.length === 0 && list.length === 0) {
      void hydrate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { list, topRisky, profile, riskEvolution, heatmap, isLoading, error, selectHost };
}
