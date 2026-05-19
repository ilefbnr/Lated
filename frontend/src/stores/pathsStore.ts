// =============================================================================
// stores/pathsStore.ts — attack paths + timeline state
// =============================================================================

import { create } from 'zustand';

import type { AttackPathDetail, AttackPathSummary, TimelineStep } from '@/types/paths';
import { pathsService } from '@/services/pathsService';

export interface PathsState {
  rows: AttackPathSummary[];
  total: number;
  detail: AttackPathDetail | null;
  timeline: TimelineStep[];
  isLoading: boolean;
  error: string | null;
  hydrate: () => Promise<void>;
  loadDetail: (pathId: string) => Promise<void>;
}

export const usePathsStore = create<PathsState>((set) => ({
  rows: [],
  total: 0,
  detail: null,
  timeline: [],
  isLoading: false,
  error: null,

  hydrate: async () => {
    set({ isLoading: true, error: null });
    try {
      const { rows, total } = await pathsService.list();
      set({ rows, total, isLoading: false });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'failed to load paths',
      });
    }
  },

  loadDetail: async (pathId) => {
    set({ isLoading: true, error: null });
    try {
      const [detail, timeline] = await Promise.all([
        pathsService.detail(pathId),
        pathsService.timeline(pathId),
      ]);
      set({ detail, timeline, isLoading: false });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'failed to load path',
      });
    }
  },
}));
