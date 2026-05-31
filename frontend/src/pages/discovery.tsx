import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';

import { GlassCard } from '@/components/ui/GlassCard';
import { useGraphData } from '@/hooks/useGraphData';
import { formatShortDate } from '@/lib/socUi';
import { discoveryService } from '@/services/discoveryService';
import { useGraphStore } from '@/stores/graphStore';
import type { DiscoveryRunResult } from '@/types/discovery';

const AttackGraphCanvas = dynamic(
  () => import('@/components/graph/AttackGraphCanvas').then((mod) => mod.AttackGraphCanvas),
  { ssr: false, loading: () => <div className="p-6 text-sm text-[rgb(var(--lated-muted))]">Loading topology...</div> },
);

export default function DiscoveryPage() {
  const { nodes, edges, summary, generatedAt } = useGraphData();
  const hydrateGraph = useGraphStore((state) => state.hydrate);
  const [history, setHistory] = useState<DiscoveryRunResult[]>([]);
  const [sourceKind, setSourceKind] = useState<'zeek' | 'pcap'>('zeek');
  const [sourceValue, setSourceValue] = useState('backend/data/demo_zeek');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadHistory();
  }, []);

  async function loadHistory() {
    try {
      const rows = await discoveryService.history();
      setHistory(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to load history');
    }
  }

  async function runDiscovery() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await discoveryService.run(sourceKind, sourceValue, 'passive');
      setMessage(`Baseline generated from ${result.source_kind} with ${result.host_count} hosts.`);
      await loadHistory();
      await hydrateGraph('baseline');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'discovery failed');
    } finally {
      setBusy(false);
    }
  }

  async function uploadAndUse(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const uploaded = await discoveryService.upload(file);
      setSourceKind(file.name.endsWith('.pcap') || file.name.endsWith('.pcapng') ? 'pcap' : 'zeek');
      setSourceValue(uploaded.stored_path);
      setMessage(`Uploaded ${uploaded.filename}. Ready to run discovery.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'upload failed');
    } finally {
      setBusy(false);
    }
  }

  const latest = history[0] ?? null;

  return (
    <div className="grid grid-cols-12 gap-6 p-6">
      <section className="col-span-12 xl:col-span-4 flex flex-col gap-6">
        <GlassCard>
          <p className="lated-eyebrow mb-3">Discovery Control</p>
          <div className="flex flex-col gap-3">
            <select
              value={sourceKind}
              onChange={(event) => setSourceKind(event.target.value as 'zeek' | 'pcap')}
              className="rounded border border-outline/70 bg-elevated px-3 py-2 text-sm text-ink outline-none transition focus:border-cyan/60"
            >
              <option value="zeek">Zeek</option>
              <option value="pcap">PCAP</option>
            </select>
            <input
              value={sourceValue}
              onChange={(event) => setSourceValue(event.target.value)}
              placeholder="source path"
              className="rounded border border-outline/70 bg-elevated px-3 py-2 font-mono text-sm text-ink outline-none transition placeholder:text-[rgb(var(--lated-faint))] focus:border-cyan/60"
            />
            <input type="file" onChange={(event) => void uploadAndUse(event)} className="text-xs text-[rgb(var(--lated-muted))]" />
            <button
              type="button"
              onClick={() => void runDiscovery()}
              disabled={busy || sourceValue.trim().length === 0}
              className="rounded border border-cyan/60 bg-cyan/10 px-3 py-2 text-xs text-cyan transition hover:bg-cyan/20 disabled:opacity-40"
            >
              {busy ? 'running...' : 'run discovery'}
            </button>
            {message && <p className="text-xs text-emerald-300">{message}</p>}
            {error && <p className="text-xs text-rose-300">{error}</p>}
          </div>
        </GlassCard>

        <GlassCard>
          <p className="lated-eyebrow mb-3">Latest Run</p>
          {latest ? (
            <div className="flex flex-col gap-1.5 text-sm text-[rgb(var(--lated-muted))]">
              <p><span className="text-ink">Source:</span> {latest.source_kind}</p>
              <p><span className="text-ink">Hosts:</span> {latest.host_count}</p>
              <p><span className="text-ink">Edges:</span> {latest.edge_count}</p>
              <p><span className="text-ink">Subnets:</span> {latest.subnet_count}</p>
              <p><span className="text-ink">Generated:</span> {formatShortDate(latest.generated_at)}</p>
            </div>
          ) : (
            <p className="text-sm text-[rgb(var(--lated-muted))]">No discovery run recorded yet.</p>
          )}
        </GlassCard>

        <GlassCard>
          <p className="lated-eyebrow mb-3">Run History</p>
          <ul className="flex max-h-80 flex-col gap-2 overflow-y-auto">
            {history.map((row) => (
              <li key={row.job_id} className="rounded-md border border-outline/70 bg-elevated px-3 py-2 text-[11px] text-[rgb(var(--lated-muted))]">
                <p className="font-mono text-ink">{row.job_id}</p>
                <p>{row.source_kind} • {row.host_count} hosts • {row.edge_count} edges</p>
              </li>
            ))}
            {history.length === 0 && <p className="text-sm text-[rgb(var(--lated-muted))]">No history yet.</p>}
          </ul>
        </GlassCard>
      </section>

      <section className="col-span-12 xl:col-span-8">
        <GlassCard>
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <p className="lated-eyebrow mb-1.5">Baseline Topology</p>
              <p className="text-sm text-[rgb(var(--lated-muted))]">
                {generatedAt ? `Generated ${formatShortDate(generatedAt)}` : 'No baseline available.'}
              </p>
            </div>
            {summary && (
              <div className="flex gap-4 flex-wrap font-mono text-[11px] text-[rgb(var(--lated-muted))]">
                <span>{summary.host_count} hosts</span>
                <span>{summary.edge_count} edges</span>
                <span>{summary.subnet_count} subnets</span>
              </div>
            )}
          </div>
          <div className="mt-4 h-[420px]">
            <AttackGraphCanvas nodes={nodes} edges={edges} />
          </div>
        </GlassCard>
      </section>
    </div>
  );
}
