// =============================================================================
// pages/timeline.tsx — Recon -> LM Timeline
// =============================================================================

import { useEffect } from 'react';
import clsx from 'clsx';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { usePaths } from '@/hooks/usePaths';
import { formatPercent, formatShortDate } from '@/lib/socUi';
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
  }, [loadDetail, rows, selectedPathId, setSelectedPath]);

  const handleSelect = (pathId: string) => {
    setSelectedPath(pathId);
    void loadDetail(pathId);
  };

  return (
    <div className="grid grid-cols-12 gap-6 p-6">
      <section className="col-span-12 xl:col-span-4">
        <GlassCard className="h-full">
          <p className="lated-eyebrow mb-3">Attack Paths</p>
          {isLoading && rows.length === 0 && <p className="text-sm text-[rgb(var(--lated-muted))]">loading paths...</p>}
          {error && <p className="text-sm text-rose-300">{error}</p>}
          {!isLoading && rows.length === 0 && <p className="text-sm text-[rgb(var(--lated-muted))]">No correlated paths yet.</p>}

          <ul className="flex flex-col gap-2">
            {rows.map((path) => {
              const active = path.path_id === selectedPathId;
              return (
                <li key={path.path_id}>
                  <button
                    type="button"
                    onClick={() => handleSelect(path.path_id)}
                    className={clsx(
                      'w-full rounded-md border px-3 py-2.5 text-left transition',
                      active
                        ? 'border-cyan/60 bg-cyan/10'
                        : 'border-outline/70 bg-elevated hover:border-cyan/40',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[11px] text-ink">{path.path_id}</span>
                      <span className="font-mono text-[11px] text-cyan">{formatPercent(path.path_confidence)}</span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-[rgb(var(--lated-muted))]">{path.hosts.length} hosts . {path.alert_count} alerts</p>
                  </button>
                </li>
              );
            })}
          </ul>
        </GlassCard>
      </section>

      <section className="col-span-12 xl:col-span-8 flex flex-col gap-4">
        {detail ? (
          <GlassCard>
            <div className="flex items-center gap-3 flex-wrap">
              <p className="font-mono text-sm text-ink">{detail.path_id}</p>
              <NeonBadge tone="violet">{formatPercent(detail.path_confidence)} confidence</NeonBadge>
              {detail.mitre_tactic_chain.map((tactic) => (
                <NeonBadge key={tactic} tone="cyan">{tactic}</NeonBadge>
              ))}
              <span className="ml-auto text-[11px] text-[rgb(var(--lated-muted))]">{formatShortDate(detail.created_at)}</span>
            </div>
          </GlassCard>
        ) : (
          <GlassCard>
            <p className="text-sm text-[rgb(var(--lated-muted))]">Select a path to see its timeline.</p>
          </GlassCard>
        )}

        <GlassCard className="flex-1">
          <p className="lated-eyebrow mb-3">Timeline</p>
          {timeline.length === 0 && detail !== null && <p className="text-sm text-[rgb(var(--lated-muted))]">No timeline steps recorded.</p>}
          <ol className="flex flex-col gap-3">
            {timeline.map((step) => (
              <li key={`${step.step}-${step.ts}`} className="flex items-start gap-3">
                <span className="mt-0.5 inline-flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full border border-cyan/45 bg-cyan/10 font-mono text-[11px] text-cyan">
                  {step.step}
                </span>
                <div className="min-w-0 flex-1 rounded-lg border border-outline/70 bg-elevated px-3 py-2.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-sm text-ink">{step.subject_host}</span>
                    <NeonBadge tone="muted">{step.kind}</NeonBadge>
                    {step.mitre_tags.map((tag) => (
                      <NeonBadge key={tag} tone="violet">{tag}</NeonBadge>
                    ))}
                  </div>
                  <p className="mt-1 text-[11px] text-[rgb(var(--lated-muted))]">
                    {formatShortDate(step.ts)} → {step.target_hosts.length > 0 ? step.target_hosts.join(', ') : '—'}
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
