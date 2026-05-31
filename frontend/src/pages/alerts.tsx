// =============================================================================
// pages/alerts.tsx — Triage Command Center
// =============================================================================

import { useMemo, useState } from 'react';
import {
  ActivityIcon,
  BellIcon,
  CheckCheckIcon,
  CheckIcon,
  ClockIcon,
  CrosshairIcon,
  FingerprintIcon,
  FlameIcon,
  GaugeIcon,
  SearchIcon,
  ServerIcon,
  ShieldOffIcon,
  ShieldCheckIcon,
} from 'lucide-react';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { ScoreRing } from '@/components/ui/ScoreRing';
import { SeverityDonut } from '@/components/ui/SeverityDonut';
import { ThreatPill } from '@/components/ui/ThreatPill';
import { useAlertsStream } from '@/hooks/useAlertsStream';
import { useFlows } from '@/hooks/useFlows';
import { useHostRisk } from '@/hooks/useHostRisk';
import { useUser } from '@/hooks/useUser';
import { alertsService } from '@/services/alertsService';
import { useAlertsStore } from '@/stores/alertsStore';
import type { Alert, Severity } from '@/types/alerts';
import {
  detectionKindLabel,
  formatPercent,
  formatShortDate,
  MITRE_MAP,
  RECOMMENDATIONS,
  scoreColor,
  SEVERITY_COLORS,
  tacticColor,
} from '@/lib/socUi';

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];
const PRIORITY_COLORS = {
  critical: '#F43F5E',
  high: '#FB923C',
  medium: '#FBBF24',
  low: '#60A5FA',
} as const;

export default function AlertsPage() {
  const { rows, total, isLoading, error, openCounts } = useAlertsStream();
  const { list: hosts } = useHostRisk();
  const { rows: flows } = useFlows();
  const { hasRole } = useUser();
  const updateAlert = useAlertsStore((state) => state.update);
  const [selected, setSelected] = useState<Set<Severity>>(new Set());
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const canAck = hasRole('analyst');
  const canClose = hasRole('supervisor');

  const filtered = useMemo(() => {
    const lowered = query.trim().toLowerCase();
    return rows.filter((alert) => {
      if (selected.size > 0 && !selected.has(alert.severity)) return false;
      if (!lowered) return true;
      return (
        alert.description.toLowerCase().includes(lowered)
        || alert.subject_host.toLowerCase().includes(lowered)
        || alert.alert_id.toLowerCase().includes(lowered)
        || alert.mitre_tags.join(' ').toLowerCase().includes(lowered)
      );
    });
  }, [query, rows, selected]);

  const active = useMemo(() => {
    if (filtered.length === 0) return null;
    return filtered.find((alert) => alert.alert_id === selectedId) ?? filtered[0];
  }, [filtered, selectedId]);

  const criticalOpen = rows.filter((alert) => alert.status === 'open' && alert.severity === 'critical').length;
  const distinctTechniques = new Set(rows.flatMap((alert) => alert.mitre_tags));
  const oldestOpen = rows
    .filter((alert) => alert.status === 'open')
    .sort((a, b) => +new Date(a.created_at) - +new Date(b.created_at))[0] ?? null;
  const dwellMinutes = oldestOpen
    ? Math.max(0, Math.round((Date.now() - +new Date(oldestOpen.created_at)) / 60000))
    : 0;

  const toggleSeverity = (severity: Severity) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(severity)) next.delete(severity);
      else next.add(severity);
      return next;
    });
  };

  const handleAck = async (alertId: string) => {
    setActionBusy(`ack:${alertId}`);
    setActionError(null);
    try {
      const updated = await alertsService.ack(alertId);
      updateAlert(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'ack failed');
    } finally {
      setActionBusy(null);
    }
  };

  const handleClose = async (alertId: string) => {
    setActionBusy(`close:${alertId}`);
    setActionError(null);
    try {
      const updated = await alertsService.close(alertId, 'true_positive');
      updateAlert(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'close failed');
    } finally {
      setActionBusy(null);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-5">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <p className="section-title !mb-0">Alert Triage . Command Center</p>
          <span className="inline-flex items-center gap-2 font-mono text-[11px] text-[rgb(var(--lated-muted))]">
            <span className="lated-anim-pulse-dot h-1.5 w-1.5 rounded-full bg-cyan" />
            live stream
          </span>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            {SEVERITIES.map((severity) => {
              const isOn = selected.has(severity);
              return (
                <button
                  key={severity}
                  type="button"
                  onClick={() => toggleSeverity(severity)}
                  className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.06em] transition"
                  style={{
                    borderColor: isOn ? SEVERITY_COLORS[severity] : 'rgb(var(--lated-outline))',
                    color: isOn ? SEVERITY_COLORS[severity] : 'rgb(var(--lated-muted))',
                    background: isOn ? `${SEVERITY_COLORS[severity]}1F` : 'transparent',
                  }}
                >
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: SEVERITY_COLORS[severity] }} />
                  {severity}
                  <span className="font-mono opacity-70">{rows.filter((alert) => alert.severity === severity).length}</span>
                </button>
              );
            })}
          </div>

          <div className="relative">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="filter alerts..."
              className="w-[190px] rounded-md border border-outline/70 bg-elevated px-3 py-2 pr-8 font-mono text-xs text-ink outline-none transition placeholder:text-[rgb(var(--lated-faint))] focus:border-cyan/60"
            />
            <SearchIcon size={13} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[rgb(var(--lated-faint))]" />
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <GlassCard glow className="flex min-w-[230px] items-center gap-4 px-[18px] py-3">
          <SeverityDonut counts={openCounts} size={78} />
          <div className="flex flex-col gap-1">
            <p className="lated-eyebrow">Severity Mix</p>
            <span className="font-mono text-2xl text-ink">{total}</span>
            <span className="text-[11px] text-[rgb(var(--lated-muted))]">alerts in window</span>
          </div>
        </GlassCard>
        <KpiTile icon={<BellIcon size={13} />} label="Open" value={rows.filter((alert) => alert.status === 'open').length} sub="untriaged" color="rgb(var(--lated-cyan))" />
        <KpiTile icon={<FlameIcon size={13} />} label="Critical" value={criticalOpen} sub="open" color="#F43F5E" />
        <KpiTile icon={<FingerprintIcon size={13} />} label="ATT&CK" value={distinctTechniques.size} sub="techniques" color="rgb(var(--lated-brand))" />
        <KpiTile icon={<ClockIcon size={13} />} label="Oldest Open" value={`${dwellMinutes}m`} sub="dwell" color="#FBBF24" />
      </div>

      {actionError && (
        <GlassCard className="border border-rose-400/60 px-4 py-3">
          <p className="text-xs text-rose-300">{actionError}</p>
        </GlassCard>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[5fr_7fr]">
        <GlassCard className="flex min-h-0 flex-col overflow-hidden p-0">
          <div className="flex items-center justify-between px-4 pb-2 pt-4">
            <p className="lated-eyebrow">Alert Stream . {filtered.length}</p>
            <span className="font-mono text-[10px] text-[rgb(var(--lated-faint))]">sorted by recency</span>
          </div>
          <div className="flex-1 overflow-y-auto px-2 pb-2">
            {isLoading && <p className="px-4 py-6 text-sm text-[rgb(var(--lated-muted))]">loading alerts...</p>}
            {error && <p className="px-4 py-6 text-sm text-rose-300">{error}</p>}
            {!isLoading && filtered.length === 0 && <p className="px-4 py-6 text-sm text-[rgb(var(--lated-muted))]">No alerts match.</p>}

            <ul className="flex flex-col gap-1.5">
              {filtered.map((alert) => (
                <AlertRow
                  key={alert.alert_id}
                  alert={alert}
                  active={alert.alert_id === active?.alert_id}
                  onSelect={() => setSelectedId(alert.alert_id)}
                />
              ))}
            </ul>
          </div>
        </GlassCard>

        {active ? (
          <AlertDetailPanel
            alert={active}
            hosts={hosts}
            flows={flows}
            canAck={canAck}
            canClose={canClose}
            actionBusy={actionBusy}
            onAck={() => void handleAck(active.alert_id)}
            onClose={() => void handleClose(active.alert_id)}
          />
        ) : (
          <GlassCard className="flex items-center justify-center text-sm text-[rgb(var(--lated-muted))]">
            Select an alert to investigate.
          </GlassCard>
        )}
      </div>
    </div>
  );
}

interface KpiTileProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}

function KpiTile({ icon, label, value, sub, color = 'rgb(var(--lated-ink))' }: KpiTileProps) {
  return (
    <GlassCard className="min-w-[170px] flex-1 px-4 py-[14px]">
      <div className="flex items-center gap-2 text-[rgb(var(--lated-muted))]">
        {icon}
        <span className="lated-eyebrow">{label}</span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="font-mono text-[28px] leading-none" style={{ color }}>{value}</span>
        {sub && <span className="text-[11px] text-[rgb(var(--lated-muted))]">{sub}</span>}
      </div>
    </GlassCard>
  );
}

interface AlertRowProps {
  alert: Alert;
  active: boolean;
  onSelect: () => void;
}

function AlertRow({ alert, active, onSelect }: AlertRowProps) {
  const severityColor = SEVERITY_COLORS[alert.severity];
  const isClosed = alert.status === 'closed';
  const isCritical = alert.status === 'open' && alert.severity === 'critical';

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className={isCritical ? 'lated-anim-critical' : undefined}
        style={{
          width: '100%',
          textAlign: 'left',
          display: 'block',
          padding: '11px 13px 11px 14px',
          borderRadius: 8,
          border: `1px solid ${active ? 'rgb(var(--lated-cyan) / 0.55)' : 'rgb(var(--lated-outline))'}`,
          background: active ? 'rgb(var(--lated-cyan) / 0.09)' : 'rgb(var(--lated-elevated))',
          boxShadow: `inset 3px 0 0 ${severityColor}`,
          opacity: isClosed ? 0.62 : 1,
          transition: 'border-color 150ms, background 150ms',
        }}
      >
        <div className="mb-1 flex items-center gap-2 flex-wrap">
          <ThreatPill severity={alert.severity} />
          <NeonBadge tone="muted">{detectionKindLabel(alert.kind)}</NeonBadge>
          {alert.status !== 'open' && <NeonBadge tone={isClosed ? 'violet' : 'cyan'}>{alert.status}</NeonBadge>}
          <span className="ml-auto font-mono text-xs" style={{ color: severityColor }}>{formatPercent(alert.score)}</span>
        </div>
        <p className="text-sm leading-[1.4] text-ink">{alert.description}</p>
        <div className="mt-1.5 flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[10.5px] text-[rgb(var(--lated-muted))]">{alert.subject_host}</span>
          <span className="text-[rgb(var(--lated-faint))]">.</span>
          <span className="font-mono text-[10.5px] text-[rgb(var(--lated-faint))]">{formatShortDate(alert.created_at)}</span>
          {alert.mitre_tags.slice(0, 3).map((tag) => {
            const meta = MITRE_MAP[tag];
            const color = tacticColor(meta?.tactic);
            return (
              <span
                key={tag}
                className="rounded px-1.5 py-[1px] font-mono text-[9.5px]"
                style={{ color, border: `1px solid ${color}55`, background: `${color}14` }}
              >
                {tag}
              </span>
            );
          })}
        </div>
      </button>
    </li>
  );
}

interface AlertDetailPanelProps {
  alert: Alert;
  hosts: ReturnType<typeof useHostRisk>['list'];
  flows: ReturnType<typeof useFlows>['rows'];
  canAck: boolean;
  canClose: boolean;
  actionBusy: string | null;
  onAck: () => void;
  onClose: () => void;
}

function AlertDetailPanel({ alert, hosts, flows, canAck, canClose, actionBusy, onAck, onClose }: AlertDetailPanelProps) {
  const severityColor = SEVERITY_COLORS[alert.severity];
  const currentScoreColor = scoreColor(alert.score);
  const isOpen = alert.status === 'open';
  const isClosed = alert.status === 'closed';
  const host = hosts.find((entry) => entry.hostname === alert.subject_host || entry.host_id === alert.subject_host) ?? null;
  const relatedFlows = host === null
    ? []
    : flows.filter((flow) => host.ip_addresses.includes(flow.src_host) || host.ip_addresses.includes(flow.dst_host)).slice(0, 4);
  const recommendations = RECOMMENDATIONS[alert.kind] ?? [];
  const ackBusy = actionBusy === `ack:${alert.alert_id}`;
  const closeBusy = actionBusy === `close:${alert.alert_id}`;

  return (
    <GlassCard glow className="flex min-h-0 flex-col overflow-hidden p-0">
      <div className="flex-1 overflow-y-auto p-5">
        <div className="flex items-start gap-4">
          <ScoreRing value={alert.score} size={92} stroke={7} color={currentScoreColor} />
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex items-center gap-2 flex-wrap">
              <ThreatPill severity={alert.severity} />
              <NeonBadge tone="muted">{detectionKindLabel(alert.kind)}</NeonBadge>
              {alert.status !== 'open' && <NeonBadge tone={isClosed ? 'violet' : 'cyan'}>{alert.status}</NeonBadge>}
              <span className="ml-auto font-mono text-[11px] text-[rgb(var(--lated-faint))]">{alert.alert_id}</span>
            </div>
            <p className="text-base leading-[1.45] text-ink">{alert.description}</p>
            <div className="mt-3 flex gap-6 flex-wrap">
              <MetaBlock icon={<ServerIcon size={11} />} label="subject host" value={alert.subject_host} />
              <MetaBlock icon={<ClockIcon size={11} />} label="first seen" value={formatShortDate(alert.created_at)} />
              <MetaBlock icon={<GaugeIcon size={11} />} label="confidence" value={formatPercent(alert.score)} valueColor={severityColor} />
            </div>
          </div>
        </div>

        <section className="mt-6">
          <div className="mb-3 flex items-center gap-2">
            <CrosshairIcon size={13} className="text-brand" />
            <p className="lated-eyebrow">ATT&CK Mapping</p>
          </div>
          {alert.mitre_tags.length === 0 ? (
            <p className="text-sm text-[rgb(var(--lated-muted))]">No techniques mapped for this alert.</p>
          ) : (
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {alert.mitre_tags.map((tag) => {
                const meta = MITRE_MAP[tag] ?? { name: tag, tactic: 'Unknown' };
                const color = tacticColor(meta.tactic);
                return (
                  <div
                    key={tag}
                    className="rounded-lg border-l-[3px] px-3 py-2"
                    style={{ borderColor: color, borderTop: `1px solid ${color}40`, borderRight: `1px solid ${color}40`, borderBottom: `1px solid ${color}40`, background: `${color}0E` }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs" style={{ color }}>{tag}</span>
                      <span className="text-[9px] uppercase tracking-[0.06em]" style={{ color }}>{meta.tactic}</span>
                    </div>
                    <p className="mt-1 text-sm text-ink">{meta.name}</p>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {recommendations.length > 0 && (
          <section className="mt-6">
            <div className="mb-3 flex items-center gap-2">
              <ShieldCheckIcon size={13} className="text-cyan" />
              <p className="lated-eyebrow">Recommended Containment</p>
            </div>
            <ol className="flex flex-col gap-2">
              {recommendations.map((recommendation, index) => (
                <li key={recommendation.action} className="flex items-center gap-3 rounded-md border border-outline/70 bg-elevated px-3 py-2">
                  <span className="w-3 font-mono text-[11px] text-[rgb(var(--lated-faint))]">{index + 1}</span>
                  <span
                    className="h-[7px] w-[7px] rounded-full"
                    style={{ background: PRIORITY_COLORS[recommendation.priority], boxShadow: `0 0 6px ${PRIORITY_COLORS[recommendation.priority]}88` }}
                  />
                  <span className="flex-1 text-sm text-ink">{recommendation.action}</span>
                  <span className="text-[9px] uppercase tracking-[0.06em]" style={{ color: PRIORITY_COLORS[recommendation.priority] }}>
                    {recommendation.priority}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        )}

        {relatedFlows.length > 0 && (
          <section className="mt-6">
            <div className="mb-3 flex items-center gap-2">
              <ActivityIcon size={13} className="text-[rgb(var(--lated-muted))]" />
              <p className="lated-eyebrow">Related Flows . {relatedFlows.length}</p>
            </div>
            <div className="overflow-hidden rounded-lg border border-outline/70">
              <table className="w-full border-collapse font-mono text-[11px]">
                <thead>
                  <tr className="bg-elevated">
                    {['source', 'dest', 'proto', 'bytes', 'susp'].map((heading) => (
                      <th
                        key={heading}
                        className="px-3 py-2 text-left text-[9px] font-medium uppercase tracking-[0.08em] text-[rgb(var(--lated-faint))]"
                        style={{ textAlign: heading === 'bytes' || heading === 'susp' ? 'right' : 'left' }}
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {relatedFlows.map((flow) => (
                    <tr key={flow.flow_id} className="border-t border-outline/70">
                      <td className="px-3 py-2 text-ink">{flow.src_host}:{flow.src_port}</td>
                      <td className="px-3 py-2 text-[rgb(var(--lated-muted))]">{flow.dst_host}:{flow.dst_port}</td>
                      <td className="px-3 py-2 uppercase text-cyan">{flow.protocol}</td>
                      <td className="px-3 py-2 text-right text-[rgb(var(--lated-muted))]">{(flow.byte_count / 1024).toFixed(1)}K</td>
                      <td className="px-3 py-2 text-right" style={{ color: scoreColor(flow.suspicion) }}>{formatPercent(flow.suspicion)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-outline/70 bg-[var(--lated-glass-bg)] px-5 py-3">
        <span className="mr-auto inline-flex items-center gap-2 text-[11px] text-[rgb(var(--lated-muted))]">
          <span className="h-[7px] w-[7px] rounded-full" style={{ background: isClosed ? '#A78BFA' : alert.status === 'ack' ? '#22D3EE' : severityColor }} />
          {isClosed ? 'Closed' : alert.status === 'ack' ? 'Acknowledged' : 'Awaiting triage'}
        </span>
        {canAck && isOpen && (
          <button
            type="button"
            onClick={onAck}
            disabled={ackBusy}
            className="rounded border border-cyan/60 bg-cyan/10 px-3 py-1.5 text-xs text-cyan transition hover:bg-cyan/20 disabled:opacity-40"
          >
            <span className="inline-flex items-center gap-1.5"><CheckIcon size={12} /> acknowledge</span>
          </button>
        )}
        {canClose && !isClosed && (
          <button
            type="button"
            onClick={onClose}
            disabled={closeBusy}
            className="rounded border border-brand/60 bg-brand/10 px-3 py-1.5 text-xs text-brand transition hover:bg-brand/20 disabled:opacity-40"
          >
            <span className="inline-flex items-center gap-1.5"><CheckCheckIcon size={12} /> close</span>
          </button>
        )}
        <button type="button" className="rounded border border-rose-400/60 bg-rose-400/10 px-3 py-1.5 text-xs text-rose-300 transition hover:bg-rose-400/20">
          <span className="inline-flex items-center gap-1.5"><ShieldOffIcon size={12} /> isolate host</span>
        </button>
      </div>
    </GlassCard>
  );
}

interface MetaBlockProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  valueColor?: string;
}

function MetaBlock({ icon, label, value, valueColor = 'rgb(var(--lated-ink))' }: MetaBlockProps) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="inline-flex items-center gap-1.5 text-[9px] uppercase tracking-[0.14em] text-[rgb(var(--lated-faint))]">
        {icon}
        {label}
      </span>
      <span className="font-mono text-[12.5px]" style={{ color: valueColor }}>{value}</span>
    </div>
  );
}
