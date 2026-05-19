// =============================================================================
// stores/graphStore.ts — attack-graph state
// =============================================================================

import { create } from 'zustand';

import type { GraphEdge, GraphNode, GraphPayload } from '@/types/graph';
import { graphService } from '@/services/graphService';

export interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  generatedAt: string;
  summary: GraphPayload['summary'];
  isLoading: boolean;
  error: string | null;
  hydrate: (kind?: 'baseline' | 'latest') => Promise<void>;
  applyDelta: (payload: GraphPayload) => void;
}

function dedupeById<T extends { data: { id: string } }>(items: T[]): T[] {
  const map = new Map<string, T>();
  for (const item of items) map.set(item.data.id, item);
  return Array.from(map.values());
}

export const useGraphStore = create<GraphState>((set, get) => ({
  nodes: [],
  edges: [],
  generatedAt: '',
  summary: undefined,
  isLoading: false,
  error: null,

  hydrate: async (kind = 'baseline') => {
    set({ isLoading: true, error: null });
    try {
      const payload = kind === 'latest'
        ? await graphService.latest().catch(() => graphService.baseline())
        : await graphService.baseline();
      set({
        nodes: payload.nodes,
        edges: payload.edges,
        generatedAt: payload.generated_at,
        summary: payload.summary,
        isLoading: false,
      });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'failed to load graph',
        summary: undefined,
      });
    }
  },

  applyDelta: (payload) => {
    const nextNodes = dedupeById([...get().nodes, ...payload.nodes]);
    const nextEdges = dedupeById([...get().edges, ...payload.edges]);
    set({
      nodes: nextNodes,
      edges: nextEdges,
      generatedAt: payload.generated_at,
      summary: payload.summary ?? get().summary,
    });
  },
}));
