// =============================================================================
// pages/hosts.tsx — Host Risk Dashboard
// =============================================================================

import { useEffect } from 'react';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { Sparkline } from '@/components/ui/Sparkline';
import { useHostRisk } from '@/hooks/useHostRisk';
import { formatPercent, formatShortDate, formatShortTime } from '@/lib/socUi';
import { useUIStore } from '@/stores/uiStore';

export default function HostsPage() {
  const { topRisky, profile, riskEvolution, heatmap, isLoading, error, selectHost } = useHostRisk();
  const selectedHostId = useUIStore((state) => state.selectedHostId);
  const setSelectedHost = useUIStore((state) => state.setSelectedHost);

  useEffect(() => {
    if (selectedHostId !== null) {
      void selectHost(selectedHostId);
      return;
    }

    const first = topRisky[0];
    if (first) {
      setSelectedHost(first.host_id);
      void selectHost(first.host_id);
    }
  }, [selectHost, selectedHostId, setSelectedHost, topRisky]);

  const handleSelect = (hostId: string) => {
    setSelectedHost(hostId);
    void selectHost(hostId);
  };

  return (
    <div className="grid grid-cols-12 gap-6 p-6">
      <section className="col-span-12 xl:col-span-7">
        <GlassCard className="h-full">
          <p className="lated-eyebrow mb-3">Host Risk</p>
          {isLoading && topRisky.length === 0 && <p className="text-sm text-[rgb(var(--lated-muted))]">loading hosts...</p>}
          {error && <p className="text-sm text-rose-300">{error}</p>}
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-[0.06em] text-[rgb(var(--lated-muted))]">
                <th className="py-2">Host</th>
                <th className="py-2">Subnet</th>
                <th className="py-2">OS</th>
                <th className="py-2 text-right">Risk</th>
                <th className="py-2 text-right">Active</th>
              </tr>
            </thead>
            <tbody>
              {topRisky.map((host) => {
                const active = host.host_id === selectedHostId;
                return (
                  <tr
                    key={host.host_id}
                    onClick={() => handleSelect(host.host_id)}
                    className={active ? 'cursor-pointer border-l-2 border-cyan bg-cyan/10' : 'cursor-pointer transition hover:bg-elevated'}
                  >
                    <td className="py-2 pl-2 pr-2 font-mono text-xs text-ink">{host.hostname ?? host.host_id}</td>
                    <td className="py-2 pr-2 font-mono text-[11px] text-[rgb(var(--lated-muted))]">{host.subnet ?? '—'}</td>
                    <td className="py-2 pr-2 text-[11px] text-[rgb(var(--lated-muted))]">{profile?.host_id === host.host_id ? (profile.os_guess ?? 'unknown') : '—'}</td>
                    <td className="py-2 pr-2 text-right font-mono text-cyan">{formatPercent(host.current_risk)}</td>
                    <td className="py-2 text-right text-[rgb(var(--lated-muted))]">{host.active_alerts}</td>
                  </tr>
                );
              })}
              {topRisky.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={5} className="py-4 text-sm text-[rgb(var(--lated-muted))]">No hosts yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </GlassCard>
      </section>

      <section className="col-span-12 xl:col-span-5 flex flex-col gap-6">
        <GlassCard>
          <p className="lated-eyebrow mb-3">Host Profile</p>
          {profile ? (
            <div className="flex flex-col gap-2 text-sm">
              <div className="flex items-center gap-2">
                <p className="font-mono text-[14px] text-ink">{profile.hostname ?? profile.host_id}</p>
                <NeonBadge tone="muted">{profile.os_guess ?? 'unknown'}</NeonBadge>
              </div>
              <p className="text-xs text-[rgb(var(--lated-muted))]">
                IPs: <span className="font-mono text-ink">{profile.ip_addresses.join(', ')}</span>
              </p>
              <p className="text-xs text-[rgb(var(--lated-muted))]">Subnet: {profile.subnet ?? '—'}</p>
              <p className="text-[11px] text-[rgb(var(--lated-muted))]">First seen: {formatShortDate(profile.first_seen)}</p>
              <p className="text-[11px] text-[rgb(var(--lated-muted))]">Last seen: {formatShortDate(profile.last_seen)}</p>
            </div>
          ) : (
            <p className="text-sm text-[rgb(var(--lated-muted))]">Select a host to inspect.</p>
          )}
        </GlassCard>

        <GlassCard>
          <p className="lated-eyebrow mb-3">Risk Evolution (24h)</p>
          {riskEvolution.length === 0 ? (
            <p className="text-sm text-[rgb(var(--lated-muted))]">No history points.</p>
          ) : (
            <>
              {(() => {
                const firstPoint = riskEvolution[0];
                const lastPoint = riskEvolution[riskEvolution.length - 1];
                const peak = Math.max(...riskEvolution.map((point) => point.risk));
                return (
                  <>
              <Sparkline data={riskEvolution.map((point) => point.risk)} width={360} height={70} color="rgb(var(--lated-cyan) / 1)" />
              <div className="mt-1 flex justify-between font-mono text-[10px] text-[rgb(var(--lated-muted))]">
                <span>{firstPoint ? formatShortTime(firstPoint.ts) : '--:--'}</span>
                <span className="text-cyan">peak {formatPercent(peak)}</span>
                <span>{lastPoint ? formatShortTime(lastPoint.ts) : '--:--'}</span>
              </div>
                  </>
                );
              })()}
            </>
          )}
        </GlassCard>

        <GlassCard>
          <p className="lated-eyebrow mb-3">Communication Heatmap</p>
          {heatmap.length === 0 ? (
            <p className="text-sm text-[rgb(var(--lated-muted))]">No neighbor traffic recorded.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {heatmap.map((cell) => (
                <li key={cell.neighbor_host_id} className="flex items-center gap-3 text-[11px]">
                  <span className="w-[110px] truncate font-mono text-ink">{cell.neighbor_host_id}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-elevated">
                    <div
                      className="h-full rounded-full bg-[linear-gradient(90deg,rgb(var(--lated-cyan)),rgb(var(--lated-neon)))]"
                      style={{ width: `${cell.intensity * 100}%` }}
                    />
                  </div>
                  <span className="w-10 text-right font-mono text-cyan">{formatPercent(cell.intensity)}</span>
                </li>
              ))}
            </ul>
          )}
        </GlassCard>
      </section>
    </div>
  );
}
