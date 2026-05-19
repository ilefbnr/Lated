// =============================================================================
// pages/timeline.tsx — RECON -> LM TIMELINE
// =============================================================================

import { useEffect } from 'react';
import clsx from 'clsx';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { usePaths } from '@/hooks/usePaths';
import { useUIStore } from '@/stores/uiStore';

export default function TimelinePage() {
  const { rows, detail, timeline, isLoading, error, loadDetail } = usePaths();
  const selectedPathId = useUIStore((state) => state.selectedPathId);
  const setSelectedPath = useUIStore((state) => state.setSelectedPath);

  useEffect(() => {
    if (selectedPathId !== null) {
      void loadDetail(selectedPathId);
      return;
    }
    const first = rows[0];
    if (first) {
      setSelectedPath(first.path_id);
      void loadDetail(first.path_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows]);

  const handleSelect = (pathId: string) => {
    setSelectedPath(pathId);
    void loadDetail(pathId);
  };

  return (
    <div className="grid grid-cols-12 gap-6 p-6">
      <section className="col-span-12 xl:col-span-4">
        <GlassCard className="h-full">
          <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Attack Paths</p>
          {isLoading && rows.length === 0 && <p className="text-sm text-muted">loading paths…</p>}
          {error && <p className="text-sm text-rose-300">{error}</p>}
          {!isLoading && rows.length === 0 && (
            <p className="text-sm text-muted">No correlated paths yet.</p>
          )}
          <ul className="flex flex-col gap-2">
            {rows.map((path) => {
              const active = path.path_id === selectedPathId;
              return (
                <li key={path.path_id}>
                  <button
                    onClick={() => handleSelect(path.path_id)}
                    className={clsx(
                      'w-full text-left px-3 py-2 rounded border transition-colors',
                      active
                        ? 'border-cyan/60 bg-cyan/10'
                        : 'border-outline/40 bg-elevated/40 hover:border-cyan/40',
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-ink truncate">{path.path_id}</span>
                      <span className="font-mono text-xs text-cyan">
                        {(path.path_confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-[11px] text-muted truncate">
                      {path.hosts.length} hosts · {path.alert_count} alerts
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
        </GlassCard>
      </section>

      <section className="col-span-12 xl:col-span-8 flex flex-col gap-4">
        <GlassCard>
          {detail ? (
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm text-ink font-mono">{detail.path_id}</p>
              <NeonBadge tone="violet">{(detail.path_confidence * 100).toFixed(0)}% confidence</NeonBadge>
              {detail.mitre_tactic_chain.map((tag) => (
                <NeonBadge key={tag} tone="cyan">{tag}</NeonBadge>
              ))}
              <span className="text-xs text-muted ml-auto">
                {new Date(detail.created_at).toLocaleString()}
              </span>
            </div>
          ) : (
            <p className="text-sm text-muted">Select a path to see its timeline.</p>
          )}
        </GlassCard>

        <GlassCard className="flex-1">
          <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Timeline</p>
          {timeline.length === 0 && detail !== null && (
            <p className="text-sm text-muted">No timeline steps recorded.</p>
          )}
          <ol className="flex flex-col gap-3">
            {timeline.map((step) => (
              <li key={`${step.step}-${step.ts}`} className="flex gap-3 items-start">
                <span className="mt-1 inline-flex items-center justify-center w-6 h-6 rounded-full bg-cyan/10 text-cyan text-xs font-mono">
                  {step.step}
                </span>
                <div className="flex-1 min-w-0 px-3 py-2 rounded border border-outline/40 bg-elevated/40">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-sm text-ink truncate">{step.subject_host}</span>
                    <NeonBadge tone="muted">{step.kind}</NeonBadge>
                    {step.mitre_tags.map((tag) => (
                      <NeonBadge key={tag} tone="violet">{tag}</NeonBadge>
                    ))}
                  </div>
                  <p className="text-[11px] text-muted mt-1">
                    {new Date(step.ts).toLocaleString()} →{' '}
                    {step.target_hosts.length > 0 ? step.target_hosts.join(', ') : '—'}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </GlassCard>
      </section>
    </div>
  );
}
