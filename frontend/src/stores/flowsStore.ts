// =============================================================================
// stores/flowsStore.ts — suspicious-flows state
// =============================================================================

import { create } from 'zustand';

import type { SuspiciousFlow } from '@/types/flows';
import { flowsService, type FlowsFilters } from '@/services/flowsService';

export interface FlowsState {
  rows: SuspiciousFlow[];
  total: number;
  filters: FlowsFilters;
  isLoading: boolean;
  error: string | null;
  hydrate: (filters?: FlowsFilters) => Promise<void>;
  setFilters: (filters: FlowsFilters) => void;
  enqueue: (flow: SuspiciousFlow) => void;
}

const MAX_ROWS = 500;

function upsert(rows: SuspiciousFlow[], next: SuspiciousFlow): SuspiciousFlow[] {
  const index = rows.findIndex((row) => row.flow_id === next.flow_id);
  if (index === -1) return [next, ...rows].slice(0, MAX_ROWS);
  const copy = rows.slice();
  copy[index] = next;
  return copy;
}

export const useFlowsStore = create<FlowsState>((set, get) => ({
  rows: [],
  total: 0,
  filters: {},
  isLoading: false,
  error: null,

  hydrate: async (filters) => {
    const merged = filters ?? get().filters;
    set({ isLoading: true, error: null, filters: merged });
    try {
      const { rows, total } = await flowsService.list(merged);
      set({ rows, total, isLoading: false });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'failed to load flows',
      });
    }
  },

  setFilters: (filters) => set({ filters }),

  enqueue: (flow) => {
    set({ rows: upsert(get().rows, flow) });
  },
}));
