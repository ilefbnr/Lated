// =============================================================================
// pages/hosts.tsx — HOST RISK DASHBOARD
// =============================================================================

import { useEffect } from 'react';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { useHostRisk } from '@/hooks/useHostRisk';
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topRisky]);

  const handleSelect = (hostId: string) => {
    setSelectedHost(hostId);
    void selectHost(hostId);
  };

  return (
    <div className="grid grid-cols-12 gap-6 p-6">
      <section className="col-span-12 xl:col-span-7">
        <GlassCard className="h-full">
          <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Host Risk</p>
          {isLoading && topRisky.length === 0 && (
            <p className="text-sm text-muted">loading hosts…</p>
          )}
          {error && <p className="text-sm text-rose-300">{error}</p>}
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wider text-muted">
              <tr>
                <th className="py-2">Host</th>
                <th className="py-2">Subnet</th>
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
                    className={
                      active
                        ? 'bg-cyan/10 cursor-pointer border-l-2 border-cyan'
                        : 'cursor-pointer hover:bg-elevated/40'
                    }
                  >
                    <td className="py-2 pr-2 truncate font-mono text-xs">
                      {host.hostname ?? host.host_id}
                    </td>
                    <td className="py-2 pr-2 text-muted">{host.subnet ?? '—'}</td>
                    <td className="py-2 pr-2 text-right font-mono text-cyan">
                      {(host.current_risk * 100).toFixed(0)}%
                    </td>
                    <td className="py-2 text-right text-muted">{host.active_alerts}</td>
                  </tr>
                );
              })}
              {topRisky.length === 0 && !isLoading && (
                <tr>
                  <td className="py-4 text-muted" colSpan={4}>No hosts yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </GlassCard>
      </section>

      <section className="col-span-12 xl:col-span-5 flex flex-col gap-6">
        <GlassCard>
          <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Host Profile</p>
          {profile ? (
            <div className="flex flex-col gap-2 text-sm">
              <div className="flex items-center gap-2">
                <p className="font-mono text-ink">{profile.hostname ?? profile.host_id}</p>
                <NeonBadge tone="muted">{profile.os_guess ?? 'unknown'}</NeonBadge>
              </div>
              <p className="text-xs text-muted">
                IPs: <span className="font-mono">{profile.ip_addresses.join(', ')}</span>
              </p>
              <p className="text-xs text-muted">Subnet: {profile.subnet ?? '—'}</p>
              <p className="text-[11px] text-muted">
                First seen: {new Date(profile.first_seen).toLocaleString()}
              </p>
              <p className="text-[11px] text-muted">
                Last seen: {new Date(profile.last_seen).toLocaleString()}
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted">Select a host to inspect.</p>
          )}
        </GlassCard>

        <GlassCard>
          <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Risk Evolution (24h)</p>
          {riskEvolution.length === 0 ? (
            <p className="text-sm text-muted">No history points.</p>
          ) : (
            <ul className="text-xs font-mono text-muted flex flex-col gap-1 max-h-40 overflow-y-auto">
              {riskEvolution.map((point, index) => (
                <li key={`${point.ts}-${index}`} className="flex justify-between">
                  <span>{new Date(point.ts).toLocaleTimeString()}</span>
                  <span className="text-cyan">{(point.risk * 100).toFixed(0)}%</span>
                </li>
              ))}
            </ul>
          )}
        </GlassCard>

        <GlassCard>
          <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Communication Heatmap</p>
          {heatmap.length === 0 ? (
            <p className="text-sm text-muted">No neighbor traffic recorded.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {heatmap.map((cell) => (
                <li
                  key={cell.neighbor_host_id}
                  className="flex items-center justify-between text-xs font-mono"
                >
                  <span className="text-ink truncate">{cell.neighbor_host_id}</span>
                  <span className="text-cyan">{(cell.intensity * 100).toFixed(0)}%</span>
                </li>
              ))}
            </ul>
          )}
        </GlassCard>
      </section>
    </div>
  );
}
