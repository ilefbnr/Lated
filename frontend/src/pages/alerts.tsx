// =============================================================================
// pages/alerts.tsx — LIVE ALERTS PANEL
// =============================================================================

import { useMemo, useState } from 'react';
import clsx from 'clsx';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { ThreatPill } from '@/components/ui/ThreatPill';
import { useAlertsStream } from '@/hooks/useAlertsStream';
import { useUser } from '@/hooks/useUser';
import { useAlertsStore } from '@/stores/alertsStore';
import { alertsService } from '@/services/alertsService';
import type { Severity } from '@/types/alerts';

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];

export default function AlertsPage() {
  const { rows, total, isLoading, error } = useAlertsStream();
  const { hasRole } = useUser();
  const updateAlert = useAlertsStore((state) => state.update);
  const [selected, setSelected] = useState<Set<Severity>>(new Set());
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const canAck = hasRole('analyst');
  const canClose = hasRole('supervisor');

  const filtered = useMemo(() => {
    if (selected.size === 0) return rows;
    return rows.filter((alert) => selected.has(alert.severity));
  }, [rows, selected]);

  const toggle = (severity: Severity) => {
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
    <div className="flex flex-col h-full p-6 gap-4">
      <GlassCard className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          {SEVERITIES.map((severity) => {
            const active = selected.has(severity);
            return (
              <button
                key={severity}
                onClick={() => toggle(severity)}
                className={clsx(
                  'text-[10px] uppercase tracking-wider px-2 py-1 rounded-full border transition-colors',
                  active
                    ? 'border-cyan/60 text-cyan bg-cyan/10'
                    : 'border-outline/60 text-muted hover:text-ink',
                )}
              >
                {severity}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-3 text-xs text-muted">
          <span>{filtered.length} shown</span>
          <span>•</span>
          <span>{total} total</span>
        </div>
      </GlassCard>

      {actionError && (
        <GlassCard className="border border-rose-400/60">
          <p className="text-xs text-rose-300">{actionError}</p>
        </GlassCard>
      )}

      <GlassCard className="flex-1 overflow-y-auto">
        {isLoading && <p className="text-sm text-muted">loading alerts…</p>}
        {error && <p className="text-sm text-rose-300">{error}</p>}
        {!isLoading && filtered.length === 0 && (
          <p className="text-sm text-muted">No alerts match the current filters.</p>
        )}
        <ul className="flex flex-col divide-y divide-outline/40">
          {filtered.map((alert) => {
            const isAcked = alert.status === 'ack' || alert.status === 'closed';
            const isClosed = alert.status === 'closed';
            const ackBusy = actionBusy === `ack:${alert.alert_id}`;
            const closeBusy = actionBusy === `close:${alert.alert_id}`;
            return (
              <li
                key={alert.alert_id}
                className="flex items-start gap-4 px-2 py-3 hover:bg-elevated/40 transition-colors"
              >
                <ThreatPill severity={alert.severity} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm text-ink truncate">{alert.description}</p>
                    <NeonBadge tone="muted">{alert.kind}</NeonBadge>
                    {alert.status !== 'open' && (
                      <NeonBadge tone={isClosed ? 'violet' : 'cyan'}>{alert.status}</NeonBadge>
                    )}
                  </div>
                  <p className="text-[11px] text-muted font-mono mt-0.5">
                    {alert.subject_host} • {new Date(alert.created_at).toLocaleString()}
                  </p>
                  {alert.mitre_tags.length > 0 && (
                    <div className="flex gap-1 mt-1 flex-wrap">
                      {alert.mitre_tags.map((tag) => (
                        <NeonBadge key={tag} tone="violet">{tag}</NeonBadge>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2 whitespace-nowrap">
                  <span className="text-xs font-mono text-cyan">
                    {(alert.score * 100).toFixed(0)}%
                  </span>
                  <div className="flex items-center gap-1">
                    {canAck && !isAcked && (
                      <button
                        onClick={() => void handleAck(alert.alert_id)}
                        disabled={ackBusy}
                        className="text-[10px] px-2 py-1 rounded border border-cyan/60 text-cyan hover:bg-cyan/10 disabled:opacity-40"
                      >
                        ack
                      </button>
                    )}
                    {canClose && !isClosed && (
                      <button
                        onClick={() => void handleClose(alert.alert_id)}
                        disabled={closeBusy}
                        className="text-[10px] px-2 py-1 rounded border border-violet/60 text-violet hover:bg-violet/10 disabled:opacity-40"
                      >
                        close
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </GlassCard>
    </div>
  );
}
