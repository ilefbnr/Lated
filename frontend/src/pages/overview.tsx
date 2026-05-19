// =============================================================================
// pages/overview.tsx — GLOBAL SOC OVERVIEW
// =============================================================================

import { motion } from 'framer-motion';
import dynamic from 'next/dynamic';
import { stagger, fadeUp } from '@/themes/cyberTheme';
import { GlassCard } from '@/components/ui/GlassCard';
import { ThreatPill } from '@/components/ui/ThreatPill';

import { useAlertsStream } from '@/hooks/useAlertsStream';
import { useGraphData } from '@/hooks/useGraphData';
import { useHostRisk } from '@/hooks/useHostRisk';

const AttackGraphCanvas = dynamic(
  () => import('@/components/graph/AttackGraphCanvas').then((mod) => mod.AttackGraphCanvas),
  { ssr: false, loading: () => <div className="text-sm text-muted p-6">Loading topology…</div> },
);

export default function OverviewPage() {
  const { rows: alerts, openCounts, isLoading: alertsLoading, error: alertsError } = useAlertsStream();
  const { topRisky, isLoading: hostsLoading, error: hostsError } = useHostRisk();
  const { nodes, edges, generatedAt, summary, isLoading: graphLoading, error: graphError } = useGraphData();

  const totalOpen = openCounts.critical + openCounts.high + openCounts.medium + openCounts.low + openCounts.info;
  const recentAlerts = alerts.slice(0, 5);
  const recentRisky = topRisky.slice(0, 5);
  const baselineHosts = nodes.slice(0, 6);

  return (
    <motion.div
      variants={stagger(0.08)}
      initial="hidden"
      animate="visible"
      className="grid grid-cols-12 gap-6 p-6"
    >
      <motion.section variants={fadeUp} className="col-span-12 lg:col-span-3">
        <GlassCard glow className="h-full flex flex-col gap-3">
          <p className="text-xs uppercase tracking-[0.25em] text-muted">Active Alerts</p>
          <div className="text-5xl font-mono text-ink">{totalOpen}</div>
          <div className="flex flex-wrap gap-2 mt-2 items-center">
            <ThreatPill severity="critical" />
            <span className="text-xs text-muted">{openCounts.critical}</span>
            <ThreatPill severity="high" />
            <span className="text-xs text-muted">{openCounts.high}</span>
            <ThreatPill severity="medium" />
            <span className="text-xs text-muted">{openCounts.medium}</span>
            <ThreatPill severity="low" />
            <span className="text-xs text-muted">{openCounts.low}</span>
          </div>
          {alertsLoading && <p className="text-xs text-muted">loading…</p>}
          {alertsError && <p className="text-xs text-rose-300">{alertsError}</p>}
        </GlassCard>
      </motion.section>

      <motion.section variants={fadeUp} className="col-span-12 lg:col-span-6">
        <GlassCard className="h-full">
          <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Recent Alerts</p>
          {recentAlerts.length === 0 && !alertsLoading && (
            <p className="text-sm text-muted">No alerts yet.</p>
          )}
          <ul className="flex flex-col gap-2">
            {recentAlerts.map((alert) => (
              <li
                key={alert.alert_id}
                className="flex items-center justify-between gap-3 px-3 py-2 rounded border border-outline/40 bg-elevated/40"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <ThreatPill severity={alert.severity} />
                  <div className="min-w-0">
                    <p className="text-sm text-ink truncate">{alert.description}</p>
                    <p className="text-[11px] text-muted font-mono">{alert.subject_host}</p>
                  </div>
                </div>
                <span className="text-xs text-muted whitespace-nowrap">
                  {new Date(alert.created_at).toLocaleTimeString()}
                </span>
              </li>
            ))}
          </ul>
        </GlassCard>
      </motion.section>

      <motion.section variants={fadeUp} className="col-span-12 lg:col-span-3">
        <GlassCard className="h-full">
          <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Top Risky Hosts</p>
          {hostsLoading && <p className="text-xs text-muted">loading…</p>}
          {hostsError && <p className="text-xs text-rose-300">{hostsError}</p>}
          <ul className="flex flex-col gap-2">
            {recentRisky.map((host) => (
              <li
                key={host.host_id}
                className="flex items-center justify-between px-3 py-2 rounded border border-outline/40 bg-elevated/40"
              >
                <div className="min-w-0">
                  <p className="text-sm text-ink truncate">{host.hostname ?? host.host_id}</p>
                  <p className="text-[11px] text-muted">{host.subnet ?? '—'}</p>
                </div>
                <span className="font-mono text-sm text-cyan">{(host.current_risk * 100).toFixed(0)}%</span>
              </li>
            ))}
            {recentRisky.length === 0 && !hostsLoading && (
              <p className="text-sm text-muted">No host risk data.</p>
            )}
          </ul>
        </GlassCard>
      </motion.section>

      <motion.section variants={fadeUp} className="col-span-12 lg:col-span-8">
        <GlassCard className="h-full flex flex-col gap-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-muted mb-2">Baseline Topology</p>
              <p className="text-sm text-muted">
                {generatedAt
                  ? `Generated ${new Date(generatedAt).toLocaleString()}`
                  : 'No baseline generated yet.'}
              </p>
            </div>
            {summary && (
              <div className="flex items-center gap-4 text-xs text-muted font-mono flex-wrap">
                <span>{summary.host_count} hosts</span>
                <span>{summary.edge_count} edges</span>
                <span>{summary.subnet_count} subnets</span>
                <span>{summary.gateway_host_ids.length} gateways</span>
              </div>
            )}
          </div>
          {graphError && <p className="text-xs text-rose-300">{graphError}</p>}
          <div className="h-[360px] min-h-[360px]">
            <AttackGraphCanvas nodes={nodes} edges={edges} />
          </div>
          {graphLoading && <p className="text-xs text-muted">loading topology…</p>}
        </GlassCard>
      </motion.section>

      <motion.section variants={fadeUp} className="col-span-12 lg:col-span-4">
        <GlassCard className="h-full">
          <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Baseline Hosts</p>
          <ul className="flex flex-col gap-2">
            {baselineHosts.map((node) => (
              <li
                key={node.data.id}
                className="px-3 py-2 rounded border border-outline/40 bg-elevated/40"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm text-ink truncate">{node.data.label ?? node.data.id}</p>
                    <p className="text-[11px] text-muted truncate">
                      {(node.data.ip_addresses ?? []).join(', ') || 'no IP'}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[11px] text-cyan">{node.data.subnet ?? '—'}</p>
                    <p className="text-[10px] text-muted">
                      {node.data.gateway ? 'gateway' : node.data.service ? 'service' : 'host'}
                    </p>
                  </div>
                </div>
              </li>
            ))}
            {baselineHosts.length === 0 && !graphLoading && (
              <p className="text-sm text-muted">No baseline hosts available.</p>
            )}
          </ul>
        </GlassCard>
      </motion.section>

      <motion.section variants={fadeUp} className="col-span-12">
        <GlassCard>
          <p className="text-xs uppercase tracking-[0.25em] text-muted mb-3">Discovered Subnets</p>
          {summary && summary.subnets.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {summary.subnets.map((subnet) => (
                <div
                  key={subnet.cidr}
                  className="px-3 py-2 rounded border border-outline/40 bg-elevated/40 text-xs text-muted"
                >
                  <span className="text-ink font-mono">{subnet.cidr}</span>
                  <span className="ml-2">{subnet.host_count} hosts</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">No subnet information available.</p>
          )}
        </GlassCard>
      </motion.section>
    </motion.div>
  );
}
