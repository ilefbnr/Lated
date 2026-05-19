// =============================================================================
// hooks/usePaths.ts — attack paths + timeline binding
// =============================================================================

import { useEffect } from 'react';

import type { AttackPathDetail, AttackPathSummary, TimelineStep } from '@/types/paths';
import { usePathsStore } from '@/stores/pathsStore';

export interface UsePaths {
  rows: AttackPathSummary[];
  total: number;
  detail: AttackPathDetail | null;
  timeline: TimelineStep[];
  isLoading: boolean;
  error: string | null;
  loadDetail: (pathId: string) => Promise<void>;
}

export function usePaths(autoSelectFirst = false): UsePaths {
  const rows = usePathsStore((state) => state.rows);
  const total = usePathsStore((state) => state.total);
  const detail = usePathsStore((state) => state.detail);
  const timeline = usePathsStore((state) => state.timeline);
  const isLoading = usePathsStore((state) => state.isLoading);
  const error = usePathsStore((state) => state.error);
  const hydrate = usePathsStore((state) => state.hydrate);
  const loadDetail = usePathsStore((state) => state.loadDetail);

  useEffect(() => {
    if (rows.length === 0) {
      void hydrate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!autoSelectFirst) return;
    if (detail !== null) return;
    const first = rows[0];
    if (first) void loadDetail(first.path_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, autoSelectFirst]);

  return { rows, total, detail, timeline, isLoading, error, loadDetail };
}
