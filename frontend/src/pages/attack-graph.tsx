// =============================================================================
// pages/attack-graph.tsx — ATTACK GRAPH VISUALIZATION
// =============================================================================

import dynamic from 'next/dynamic';
import { useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { useGraphData } from '@/hooks/useGraphData';
import { useGraphStore } from '@/stores/graphStore';
import { usePaths } from '@/hooks/usePaths';
import type { GraphPayload } from '@/types/graph';
import { pathsService } from '@/services/pathsService';

// Cytoscape touches `window` on import — disable SSR for the canvas.
const AttackGraphCanvas = dynamic(
  () => import('@/components/graph/AttackGraphCanvas').then((mod) => mod.AttackGraphCanvas),
  { ssr: false, loading: () => <div className="text-sm text-muted p-6">Loading graph…</div> },
);

export default function AttackGraphPage() {
  const { nodes, edges, generatedAt, isLoading, error } = useGraphData();
  const refresh = useGraphStore((state) => state.hydrate);
  const { rows: paths, detail, loadDetail } = usePaths();

  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);
  const [pathSubgraph, setPathSubgraph] = useState<GraphPayload | null>(null);

  useEffect(() => {
    if (selectedPathId === null) {
      setPathSubgraph(null);
      return;
    }
    let cancelled = false;
    void loadDetail(selectedPathId);
    void pathsService.graph(selectedPathId).then((payload) => {
      if (!cancelled) setPathSubgraph(payload);
    }).catch(() => {
      if (!cancelled) setPathSubgraph(null);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPathId]);

  const highlightedHostIds = useMemo(() => {
    if (detail === null) return [];
    return detail.hosts;
  }, [detail]);

  const highlightedEdgeIds = useMemo(() => {
    if (pathSubgraph === null) return [];
    return pathSubgraph.edges.map((edge) => edge.data.id);
  }, [pathSubgraph]);

  const pivotHostIds = useMemo(() => detail?.pivot_hosts ?? [], [detail]);

  return (
    <div className="flex flex-col h-[calc(100vh-96px)] gap-4 p-4">
      <GlassCard className="flex items-center justify-between flex-wrap gap-3">
        <div className="text-xs text-muted">
          {generatedAt
            ? `Snapshot generated at ${new Date(generatedAt).toLocaleString()}`
            : 'No snapshot loaded.'}
          {error && <span className="ml-3 text-rose-300">{error}</span>}
          {isLoading && <span className="ml-3">loading…</span>}
        </div>
        <div className="flex items-center gap-2 text-xs">
          <button
            onClick={() => { setSelectedPathId(null); void refresh('baseline'); }}
            className="px-3 py-1 rounded border border-outline/60 text-muted hover:text-ink hover:border-cyan/50"
          >
            baseline
          </button>
          <button
            onClick={() => { setSelectedPathId(null); void refresh('latest'); }}
            className="px-3 py-1 rounded border border-outline/60 text-muted hover:text-ink hover:border-cyan/50"
          >
            latest snapshot
          </button>
        </div>
      </GlassCard>

      <div className="flex-1 grid grid-cols-12 gap-4 min-h-0">
        {/* Cytoscape canvas */}
        <section className="col-span-12 lg:col-span-9 min-h-[420px]">
          <AttackGraphCanvas
            nodes={nodes}
            edges={edges}
            highlightedHostIds={highlightedHostIds}
            highlightedEdgeIds={highlightedEdgeIds}
            pivotHostIds={pivotHostIds}
          />
        </section>

        {/* Attack paths sidebar */}
        <section className="col-span-12 lg:col-span-3 flex flex-col gap-3 min-h-0">
          <GlassCard className="flex-shrink-0">
            <p className="text-xs uppercase tracking-[0.25em] text-muted mb-2">Legend</p>
            <ul className="text-[11px] text-muted space-y-1">
              <li><span className="inline-block w-3 h-3 rounded-full bg-emerald-400 mr-2 align-middle" />risk &lt; 25%</li>
              <li><span className="inline-block w-3 h-3 rounded-full bg-amber-400 mr-2 align-middle" />risk 25-50%</li>
              <li><span className="inline-block w-3 h-3 rounded-full bg-orange-400 mr-2 align-middle" />risk 50-75%</li>
              <li><span className="inline-block w-3 h-3 rounded-full bg-rose-400 mr-2 align-middle" />risk ≥ 75%</li>
              <li><span className="inline-block w-3 h-3 rounded-full border-2 border-neon mr-2 align-middle" />pivot host</li>
              <li><span className="inline-block w-6 h-0.5 bg-rose-400 mr-2 align-middle" style={{ borderTop: '2px dashed' }} />attack edge</li>
            </ul>
          </GlassCard>

          <GlassCard className="flex-1 overflow-y-auto min-h-0">
            <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Attack Paths</p>
            {paths.length === 0 && (
              <p className="text-sm text-muted">
                No reconstructed paths.<br />
                <span className="text-[11px]">Run the demo seeder to generate one.</span>
              </p>
            )}
            <ul className="flex flex-col gap-2">
              {paths.map((path) => {
                const active = path.path_id === selectedPathId;
                return (
                  <li key={path.path_id}>
                    <button
                      onClick={() =>
                        setSelectedPathId(active ? null : path.path_id)
                      }
                      className={clsx(
                        'w-full text-left px-3 py-2 rounded border transition-colors',
                        active
                          ? 'border-rose-400/60 bg-rose-400/10'
                          : 'border-outline/40 bg-elevated/40 hover:border-cyan/40',
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-xs text-ink truncate">
                          {path.path_id}
                        </span>
                        <span className="font-mono text-xs text-cyan whitespace-nowrap">
                          {(path.path_confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-[11px] text-muted truncate">
                        {path.hosts.length} hosts · {path.alert_count} alerts
                      </p>
                      {path.mitre_tactic_chain.length > 0 && (
                        <div className="flex gap-1 mt-1 flex-wrap">
                          {path.mitre_tactic_chain.slice(0, 3).map((tag) => (
                            <NeonBadge key={tag} tone="violet">{tag}</NeonBadge>
                          ))}
                        </div>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </GlassCard>

          {detail && (
            <GlassCard className="flex-shrink-0">
              <p className="text-xs uppercase tracking-[0.25em] text-muted mb-2">Propagation</p>
              <p className="text-[11px] text-muted">
                Selected chain ({detail.hosts.length} hosts):
              </p>
              <ol className="mt-2 space-y-1 text-xs font-mono">
                {detail.hosts.map((host, index) => (
                  <li key={host} className="flex items-center gap-2">
                    <span className="text-muted">{index + 1}.</span>
                    <span
                      className={clsx(
                        'truncate',
                        detail.pivot_hosts.includes(host) ? 'text-neon' : 'text-ink',
                      )}
                    >
                      {host}
                    </span>
                    {detail.pivot_hosts.includes(host) && (
                      <NeonBadge tone="cyan">pivot</NeonBadge>
                    )}
                  </li>
                ))}
              </ol>
            </GlassCard>
          )}
        </section>
      </div>
    </div>
  );
}
