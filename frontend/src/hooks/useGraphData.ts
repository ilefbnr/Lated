// =============================================================================
// hooks/useGraphData.ts — attack-graph data binding
// =============================================================================

import { useEffect, useMemo } from 'react';

import type { GraphEdge, GraphNode } from '@/types/graph';
import { useGraphStore } from '@/stores/graphStore';

export interface UseGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  elements: (GraphNode | GraphEdge)[];
  generatedAt: string;
  summary: ReturnType<typeof useGraphStore.getState>['summary'];
  isLoading: boolean;
  error: string | null;
}

export function useGraphData(): UseGraphData {
  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);
  const generatedAt = useGraphStore((state) => state.generatedAt);
  const summary = useGraphStore((state) => state.summary);
  const isLoading = useGraphStore((state) => state.isLoading);
  const error = useGraphStore((state) => state.error);
  const hydrate = useGraphStore((state) => state.hydrate);

  useEffect(() => {
    if (nodes.length === 0) {
      void hydrate('baseline');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const elements = useMemo(() => [...nodes, ...edges], [nodes, edges]);

  return { nodes, edges, elements, generatedAt, summary, isLoading, error };
}
