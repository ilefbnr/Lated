// =============================================================================
// pages/flows.tsx — SUSPICIOUS FLOWS TABLE
// =============================================================================

import { useState } from 'react';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { useFlows } from '@/hooks/useFlows';
import type { FlowsFilters } from '@/services/flowsService';

const SORTS: Array<{ key: NonNullable<FlowsFilters['sort']>; label: string }> = [
  { key: 'ts',         label: 'newest' },
  { key: 'suspicion',  label: 'suspicion' },
  { key: 'bytes',      label: 'bytes' },
  { key: 'packets',    label: 'packets' },
];

export default function FlowsPage() {
  const { rows, total, isLoading, error, reload } = useFlows();
  const [q, setQ] = useState('');
  const [sort, setSort] = useState<NonNullable<FlowsFilters['sort']>>('ts');
  const [minSuspicion, setMinSuspicion] = useState(0);

  const applyFilters = () => {
    void reload({ q: q || undefined, minSuspicion: minSuspicion > 0 ? minSuspicion : undefined, sort });
  };

  return (
    <div className="flex flex-col h-full p-6 gap-4">
      <GlassCard className="flex items-center flex-wrap gap-3">
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="host search…"
          className="bg-elevated/40 border border-outline/60 text-ink text-sm rounded px-3 py-1.5 focus:outline-none focus:border-cyan/60 min-w-[200px]"
        />
        <label className="text-xs text-muted flex items-center gap-2">
          min suspicion
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minSuspicion}
            onChange={(event) => setMinSuspicion(parseFloat(event.target.value))}
          />
          <span className="font-mono text-cyan">{minSuspicion.toFixed(2)}</span>
        </label>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted">sort</span>
          {SORTS.map((option) => (
            <button
              key={option.key}
              onClick={() => setSort(option.key)}
              className={
                sort === option.key
                  ? 'px-2 py-1 rounded border border-cyan/60 text-cyan bg-cyan/10'
                  : 'px-2 py-1 rounded border border-outline/60 text-muted hover:text-ink'
              }
            >
              {option.label}
            </button>
          ))}
        </div>
        <button
          onClick={applyFilters}
          className="ml-auto px-3 py-1.5 text-xs rounded bg-cyan/10 border border-cyan/60 text-cyan hover:bg-cyan/20"
        >
          apply
        </button>
        <span className="text-xs text-muted">{rows.length}/{total}</span>
      </GlassCard>

      <GlassCard className="flex-1 overflow-y-auto">
        {isLoading && <p className="text-sm text-muted">loading flows…</p>}
        {error && <p className="text-sm text-rose-300">{error}</p>}
        {!isLoading && rows.length === 0 && (
          <p className="text-sm text-muted">No flows yet.</p>
        )}
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wider text-muted">
            <tr>
              <th className="py-2">ts</th>
              <th className="py-2">src</th>
              <th className="py-2">dst</th>
              <th className="py-2">proto</th>
              <th className="py-2 text-right">bytes</th>
              <th className="py-2 text-right">packets</th>
              <th className="py-2 text-right">suspicion</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((flow) => (
              <tr key={flow.flow_id} className="border-t border-outline/30">
                <td className="py-1.5 pr-2 text-xs text-muted whitespace-nowrap">
                  {new Date(flow.ts).toLocaleTimeString()}
                </td>
                <td className="py-1.5 pr-2 font-mono text-xs text-ink truncate">
                  {flow.src_host}:{flow.src_port}
                </td>
                <td className="py-1.5 pr-2 font-mono text-xs text-ink truncate">
                  {flow.dst_host}:{flow.dst_port}
                </td>
                <td className="py-1.5 pr-2"><NeonBadge tone="muted">{flow.protocol}</NeonBadge></td>
                <td className="py-1.5 pr-2 text-right font-mono">{flow.byte_count}</td>
                <td className="py-1.5 pr-2 text-right font-mono">{flow.packet_count}</td>
                <td className="py-1.5 text-right font-mono text-cyan">
                  {(flow.suspicion * 100).toFixed(0)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>
    </div>
  );
}
