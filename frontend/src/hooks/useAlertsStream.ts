// =============================================================================
// hooks/useAlertsStream.ts — alerts page binding
// =============================================================================

import { useEffect } from 'react';

import type { Alert, Severity } from '@/types/alerts';
import { useAlertsStore } from '@/stores/alertsStore';

export interface UseAlertsStream {
  rows: Alert[];
  total: number;
  isLoading: boolean;
  error: string | null;
  openCounts: Record<Severity, number>;
}

export function useAlertsStream(): UseAlertsStream {
  const rows = useAlertsStore((state) => state.rows);
  const total = useAlertsStore((state) => state.total);
  const isLoading = useAlertsStore((state) => state.isLoading);
  const error = useAlertsStore((state) => state.error);
  const openCounts = useAlertsStore((state) => state.openCounts);
  const hydrate = useAlertsStore((state) => state.hydrate);

  useEffect(() => {
    if (rows.length === 0) {
      void hydrate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { rows, total, isLoading, error, openCounts };
}
