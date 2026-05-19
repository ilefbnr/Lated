// =============================================================================
// hooks/useFlows.ts — suspicious flows page binding
// =============================================================================

import { useEffect } from 'react';

import type { SuspiciousFlow } from '@/types/flows';
import type { FlowsFilters } from '@/services/flowsService';
import { useFlowsStore } from '@/stores/flowsStore';

export interface UseFlows {
  rows: SuspiciousFlow[];
  total: number;
  filters: FlowsFilters;
  isLoading: boolean;
  error: string | null;
  setFilters: (filters: FlowsFilters) => void;
  reload: (filters?: FlowsFilters) => Promise<void>;
}

export function useFlows(): UseFlows {
  const rows = useFlowsStore((state) => state.rows);
  const total = useFlowsStore((state) => state.total);
  const filters = useFlowsStore((state) => state.filters);
  const isLoading = useFlowsStore((state) => state.isLoading);
  const error = useFlowsStore((state) => state.error);
  const setFilters = useFlowsStore((state) => state.setFilters);
  const hydrate = useFlowsStore((state) => state.hydrate);

  useEffect(() => {
    if (rows.length === 0) {
      void hydrate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { rows, total, filters, isLoading, error, setFilters, reload: hydrate };
}
