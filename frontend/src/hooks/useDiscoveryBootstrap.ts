// =============================================================================
// hooks/useDiscoveryBootstrap.ts — trigger passive baseline creation on entry
// =============================================================================

import { useEffect } from 'react';

import { discoveryService } from '@/services/discoveryService';
import { useGraphStore } from '@/stores/graphStore';

let bootstrapped = false;

export function useDiscoveryBootstrap(enabled: boolean): void {
  const hydrateGraph = useGraphStore((state) => state.hydrate);

  useEffect(() => {
    if (!enabled || bootstrapped) return;
    bootstrapped = true;

    void discoveryService.bootstrap()
      .catch(() => null)
      .finally(() => {
        void hydrateGraph('baseline');
      });
  }, [enabled, hydrateGraph]);
}
