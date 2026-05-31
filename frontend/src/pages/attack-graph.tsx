// =============================================================================
// pages/attack-graph.tsx — Attack Path Analysis & Reporting
// =============================================================================

import dynamic from 'next/dynamic';
import { useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';
import {
  BellIcon,
  ChevronRightIcon,
  ClockIcon,
  CornerDownRightIcon,
  CrosshairIcon,
  DownloadIcon,
  FileTextIcon,
  GitForkIcon,
  LayersIcon,
  RouteIcon,
  ServerIcon,
  Share2Icon,
} from 'lucide-react';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { ScoreRing } from '@/components/ui/ScoreRing';
import { useGraphData } from '@/hooks/useGraphData';
import { usePaths } from '@/hooks/usePaths';
import {
  formatPercent,
  formatShortDate,
  formatShortTime,
  MITRE_MAP,
  scoreColor,
  tacticColor,
} from '@/lib/socUi';
import { useGraphStore } from '@/stores/graphStore';
import type { GraphPayload } from '@/types/graph';
import { pathsService } from '@/services/pathsService';
import { baselineService, type BaselineStatus } from '@/services/baselineService';

const AttackGraphCanvas = dynamic(
  () => import('@/components/graph/AttackGraphCanvas').then((mod) => mod.AttackGraphCanvas),
  { ssr: false, loading: () => <div className="p-6 text-sm text-[rgb(var(--lated-muted))]">Loading graph...</div> },
);

export default function AttackGraphPage() {
  const { nodes, edges, generatedAt, isLoading, error } = useGraphData();
  const refresh = useGraphStore((state) => state.hydrate);
  const { rows: paths, detail, timeline, loadDetail } = usePaths();

  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);
  const [pathSubgraph, setPathSubgraph] = useState<GraphPayload | null>(null);
  const [baseline, setBaseline] = useState<BaselineStatus | null>(null);
  const [baselineBusy, setBaselineBusy] = useState(false);

  useEffect(() => {
    baselineService.status().then(setBaseline).catch(() => setBaseline(null));
  }, []);

  const switchBaseline = async (mode: 'learning' | 'frozen') => {
    setBaselineBusy(true);
    try {
      setBaseline(await baselineService.setMode(mode));
    } catch {
      /* role-gated or offline — leave current state */
    } finally {
      setBaselineBusy(false);
    }
  };

  useEffect(() => {
    const firstPath = paths[0];
    if (firstPath && selectedPathId === null) {
      setSelectedPathId(firstPath.path_id);
    }
  }, [paths, selectedPathId]);

  useEffect(() => {
    if (selectedPathId === null) {
      setPathSubgraph(null);
      return;
    }

    let cancelled = false;
    void loadDetail(selectedPathId);
    void pathsService.graph(selectedPathId)
      .then((payload) => {
        if (!cancelled) setPathSubgraph(payload);
      })
      .catch(() => {
        if (!cancelled) setPathSubgraph(null);
      });

    return () => {
      cancelled = true;
    };
  }, [loadDetail, selectedPathId]);

  const activePath = useMemo(
    () => paths.find((path) => path.path_id === selectedPathId) ?? null,
    [paths, selectedPathId],
  );

  const highlightedHostIds = useMemo(() => activePath?.hosts ?? [], [activePath]);
  const pivotHostIds = useMemo(() => activePath?.pivot_hosts ?? [], [activePath]);
  const highlightedEdgeIds = useMemo(() => pathSubgraph?.edges.map((edge) => edge.data.id) ?? [], [pathSubgraph]);

  const stepTimes = timeline.map((step) => +new Date(step.ts));
  const durationMinutes = stepTimes.length > 1
    ? Math.max(0, Math.round((Math.max(...stepTimes) - Math.min(...stepTimes)) / 60000))
    : 0;
  const confidenceColor = scoreColor(activePath?.path_confidence ?? 0);

  return (
    <div className="h-full overflow-y-auto">
      <div className="flex min-h-full flex-col gap-4 p-5">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-4">
            <p className="section-title !mb-0">Attack Path Analysis &amp; Reporting</p>
            <span className="font-mono text-[11px] text-[rgb(var(--lated-muted))]">
              snapshot {generatedAt ? formatShortDate(generatedAt) : 'pending'}
            </span>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1 rounded border border-outline/70 px-2 py-1">
              <span className="text-[9px] uppercase tracking-[0.1em] text-[rgb(var(--lated-faint))]">baseline</span>
              <span
                className="font-mono text-[10px]"
                style={{ color: baseline?.mode === 'frozen' ? '#34D399' : '#22D3EE' }}
              >
                {baseline ? `${baseline.mode} · ${baseline.edge_count}` : '...'}
              </span>
              <button
                type="button"
                onClick={() => void switchBaseline('learning')}
                disabled={baselineBusy}
                className="rounded px-1.5 py-0.5 text-[10px] text-cyan transition hover:bg-cyan/10 disabled:opacity-40"
              >
                learn
              </button>
              <button
                type="button"
                onClick={() => void switchBaseline('frozen')}
                disabled={baselineBusy}
                className="rounded px-1.5 py-0.5 text-[10px] text-emerald-300 transition hover:bg-emerald-400/10 disabled:opacity-40"
              >
                freeze
              </button>
            </div>
            <button
              type="button"
              onClick={() => {
                setSelectedPathId(null);
                void refresh('baseline');
              }}
              className="rounded border border-outline/70 px-3 py-1.5 text-xs text-[rgb(var(--lated-muted))] transition hover:border-brand/60 hover:text-[rgb(var(--lated-ink))]"
            >
              <span className="inline-flex items-center gap-1.5"><LayersIcon size={12} /> baseline</span>
            </button>
            <button type="button" className="rounded border border-outline/70 px-3 py-1.5 text-xs text-[rgb(var(--lated-muted))] transition hover:border-brand/60 hover:text-[rgb(var(--lated-ink))]">
              <span className="inline-flex items-center gap-1.5"><Share2Icon size={12} /> share</span>
            </button>
            <button type="button" className="rounded border border-cyan/60 bg-cyan/10 px-3 py-1.5 text-xs text-cyan transition hover:bg-cyan/20">
              <span className="inline-flex items-center gap-1.5"><FileTextIcon size={12} /> generate report</span>
            </button>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[8fr_4fr]">
          <div className="flex min-w-0 flex-col gap-4">
            <GlassCard glow className="overflow-hidden p-0">
              <div className="flex items-center justify-between px-4 pb-2 pt-3">
                <p className="lated-eyebrow">Topology . selected chain highlighted</p>
                <div className="flex items-center gap-4 font-mono text-[10px] text-[rgb(var(--lated-muted))]">
                  <span className="inline-flex items-center gap-1.5"><span className="w-4 border-t-2 border-dashed border-rose-400" /> attack edge</span>
                  <span className="inline-flex items-center gap-1.5"><span className="h-[9px] w-[9px] rounded-full border-2 border-neon" /> pivot</span>
                </div>
              </div>
              <div className="h-[400px]">
                <AttackGraphCanvas
                  nodes={nodes}
                  edges={edges}
                  highlightedHostIds={highlightedHostIds}
                  highlightedEdgeIds={highlightedEdgeIds}
                  pivotHostIds={pivotHostIds}
                />
              </div>
            </GlassCard>

            <GlassCard className="p-[18px]">
              <div className="mb-4 flex items-center gap-2">
                <CrosshairIcon size={13} className="text-brand" />
                <p className="lated-eyebrow">MITRE Kill Chain</p>
              </div>
              <KillChain detail={activePath} />
            </GlassCard>

            <GlassCard className="p-[18px]">
              <div className="mb-4 flex items-center gap-2">
                <RouteIcon size={13} className="text-cyan" />
                <p className="lated-eyebrow">Propagation Timeline . {timeline.length} steps</p>
              </div>
              <PropagationTimeline timeline={timeline} pivotHosts={pivotHostIds} />
            </GlassCard>
          </div>

          <div className="flex min-w-0 flex-col gap-4">
            <GlassCard className="p-4">
              <p className="lated-eyebrow mb-3">Detected Paths . {paths.length}</p>
              <ul className="flex flex-col gap-2">
                {paths.map((path) => (
                  <PathCard
                    key={path.path_id}
                    path={path}
                    active={path.path_id === selectedPathId}
                    onClick={() => setSelectedPathId(path.path_id)}
                  />
                ))}
              </ul>
            </GlassCard>

            {activePath !== null && (
              <GlassCard glow className="flex flex-col gap-4 p-[18px]">
                <div className="flex items-center gap-2">
                  <FileTextIcon size={13} className="text-cyan" />
                  <p className="lated-eyebrow">Incident Report . {activePath.path_id}</p>
                </div>

                <div className="flex items-center gap-4">
                  <ScoreRing value={activePath.path_confidence} size={96} stroke={8} color={confidenceColor} />
                  <p className="text-[13px] leading-[1.5] text-[rgb(var(--lated-ink))]">
                    {activePath.path_confidence >= 0.85 ? 'High-confidence' : 'Probable'} lateral-movement chain traversing{' '}
                    <strong className="text-cyan">{activePath.hosts.length} hosts</strong> across{' '}
                    <strong className="text-brand">{activePath.mitre_tactic_chain.length} tactics</strong> over{' '}
                    <strong>{durationMinutes}m</strong>.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <ReportStat icon={<ServerIcon size={11} />} label="blast radius" value={`${activePath.hosts.length} hosts`} />
                  <ReportStat icon={<GitForkIcon size={11} />} label="pivots" value={activePath.pivot_hosts.length} color="rgb(var(--lated-neon))" />
                  <ReportStat icon={<BellIcon size={11} />} label="alerts" value={activePath.alert_count} color="#FB923C" />
                  <ReportStat icon={<ClockIcon size={11} />} label="dwell" value={`${durationMinutes}m`} />
                </div>

                <div>
                  <p className="lated-eyebrow mb-2">Recommended Containment</p>
                  <ul className="flex flex-col gap-2">
                    {[
                      `Isolate pivot ${activePath.pivot_hosts[0] ?? activePath.hosts[0]}`,
                      'Rotate domain credentials used in chain',
                      'Block implicated SMB/RDP edges',
                    ].map((text, index) => (
                      <li key={text} className="flex items-center gap-2 text-[12.5px] text-[rgb(var(--lated-ink))]">
                        <span
                          className="h-[7px] w-[7px] rounded-full"
                          style={{
                            background: index === 0 ? '#F43F5E' : index === 1 ? '#FB923C' : '#FBBF24',
                            boxShadow: `0 0 6px ${index === 0 ? '#F43F5E' : index === 1 ? '#FB923C' : '#FBBF24'}99`,
                          }}
                        />
                        {text}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="flex gap-2">
                  <button type="button" className="flex-1 rounded border border-cyan/60 bg-cyan/10 px-3 py-2 text-xs text-cyan transition hover:bg-cyan/20">
                    <span className="inline-flex items-center gap-1.5"><DownloadIcon size={12} /> export PDF</span>
                  </button>
                  <button type="button" className="flex-1 rounded border border-outline/70 px-3 py-2 text-xs text-[rgb(var(--lated-muted))] transition hover:border-brand/60 hover:text-[rgb(var(--lated-ink))]">
                    <span className="inline-flex items-center gap-1.5"><Share2Icon size={12} /> STIX 2.1</span>
                  </button>
                </div>
              </GlassCard>
            )}

            {error && <p className="text-sm text-rose-300">{error}</p>}
            {isLoading && <p className="text-sm text-[rgb(var(--lated-muted))]">loading graph...</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

function KillChain({ detail }: { detail: ReturnType<typeof usePaths>['rows'][number] | null }) {
  if (detail === null || detail.mitre_tactic_chain.length === 0) {
    return <p className="text-sm text-[rgb(var(--lated-muted))]">No tactic chain available.</p>;
  }

  return (
    <div className="flex items-stretch gap-0 overflow-x-auto">
      {detail.mitre_tactic_chain.map((tactic, index) => {
        const color = tacticColor(tactic);
        return (
          <div key={`${tactic}-${index}`} className="flex items-center">
            <div className="flex min-w-[150px] flex-col gap-2">
              <div className="flex items-center gap-2">
                <span
                  className="inline-flex h-[26px] w-[26px] items-center justify-center rounded-full border font-mono text-[11px]"
                  style={{ borderColor: color, background: `${color}1F`, color }}
                >
                  {index + 1}
                </span>
                <span className="text-sm font-semibold" style={{ color }}>{tactic}</span>
              </div>
            </div>
            {index < detail.mitre_tactic_chain.length - 1 && (
              <div className="px-2 text-[rgb(var(--lated-faint))]">
                <ChevronRightIcon size={16} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

interface PropagationTimelineProps {
  timeline: ReturnType<typeof usePaths>['timeline'];
  pivotHosts: string[];
}

function PropagationTimeline({ timeline, pivotHosts }: PropagationTimelineProps) {
  if (timeline.length === 0) {
    return <p className="text-sm text-[rgb(var(--lated-muted))]">No timeline steps recorded.</p>;
  }

  return (
    <ol className="relative flex flex-col gap-4">
      <div className="absolute left-[13px] top-2 bottom-2 w-[2px] bg-[linear-gradient(180deg,#60A5FA,#F43F5E)] opacity-40" />
      {timeline.map((step, index) => {
        const leadTag = step.mitre_tags[0];
        const tactic = leadTag ? (MITRE_MAP[leadTag]?.tactic ?? step.kind) : step.kind;
        const color = tacticColor(tactic);
        const isPivot = pivotHosts.includes(step.subject_host);
        return (
          <li key={`${step.step}-${step.ts}-${index}`} className="relative flex gap-3">
            <div className="relative z-[1] shrink-0">
              <span
                className="inline-flex h-7 w-7 items-center justify-center rounded-full border-2 bg-surface font-mono text-[11px]"
                style={{ borderColor: color, color, boxShadow: isPivot ? `0 0 12px ${color}66` : undefined }}
              >
                {step.step}
              </span>
            </div>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="mb-1 flex items-center gap-2 flex-wrap">
                <span className="font-mono text-sm text-ink">{step.subject_host}</span>
                {isPivot && <NeonBadge tone="cyan">pivot</NeonBadge>}
                <span className="text-[10px] uppercase tracking-[0.06em]" style={{ color }}>{step.kind.replace(/_/g, ' ')}</span>
                <span className="ml-auto font-mono text-[10.5px] text-[rgb(var(--lated-faint))]">{formatShortTime(step.ts)}</span>
              </div>
              <div className="flex items-center gap-2 font-mono text-[11px] text-[rgb(var(--lated-muted))]">
                <CornerDownRightIcon size={12} className="text-[rgb(var(--lated-faint))]" />
                <span style={{ color }}>{step.target_hosts.join(', ') || '—'}</span>
              </div>
              {step.mitre_tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {step.mitre_tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded px-1.5 py-[1px] font-mono text-[9.5px]"
                      style={{ color, border: `1px solid ${color}55`, background: `${color}12` }}
                    >
                      {tag} . {MITRE_MAP[tag]?.name ?? ''}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function PathCard({
  path,
  active,
  onClick,
}: {
  path: ReturnType<typeof usePaths>['rows'][number];
  active: boolean;
  onClick: () => void;
}) {
  const color = scoreColor(path.path_confidence);

  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className="w-full rounded-lg border px-3 py-3 text-left transition-all"
        style={{
          borderColor: active ? `${color}88` : 'rgb(var(--lated-outline))',
          background: active ? `${color}12` : 'rgb(var(--lated-elevated))',
          boxShadow: active ? `inset 3px 0 0 ${color}` : undefined,
        }}
      >
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="font-mono text-[11.5px] text-ink">{path.path_id}</span>
          <span className="font-mono text-xs" style={{ color }}>{formatPercent(path.path_confidence)}</span>
        </div>
        <div className="mb-2 h-1 overflow-hidden rounded bg-outline/80">
          <div className="h-full rounded" style={{ width: `${path.path_confidence * 100}%`, background: `linear-gradient(90deg, ${color}55, ${color})` }} />
        </div>
        <div className="flex items-center gap-3 font-mono text-[10.5px] text-[rgb(var(--lated-muted))]">
          <span className="inline-flex items-center gap-1"><ServerIcon size={11} /> {path.hosts.length}</span>
          <span className="inline-flex items-center gap-1"><GitForkIcon size={11} /> {path.pivot_hosts.length}</span>
          <span className="inline-flex items-center gap-1"><BellIcon size={11} /> {path.alert_count}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {path.mitre_tactic_chain.map((tactic) => {
            const tacticTint = tacticColor(tactic);
            return (
              <span
                key={tactic}
                className="rounded px-1.5 py-[1px] text-[9px] uppercase tracking-[0.04em]"
                style={{ color: tacticTint, border: `1px solid ${tacticTint}44`, background: `${tacticTint}10` }}
              >
                {tactic}
              </span>
            );
          })}
        </div>
      </button>
    </li>
  );
}

function ReportStat({
  icon,
  label,
  value,
  color = 'rgb(var(--lated-ink))',
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="rounded-lg border border-outline/70 bg-elevated px-3 py-2.5">
      <span className="inline-flex items-center gap-1.5 text-[9px] uppercase tracking-[0.12em] text-[rgb(var(--lated-faint))]">
        {icon}
        {label}
      </span>
      <div className="mt-1 font-mono text-[19px]" style={{ color }}>{value}</div>
    </div>
  );
}
