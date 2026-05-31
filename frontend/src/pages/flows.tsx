// =============================================================================
// pages/flows.tsx — Suspicious Flows Table
// =============================================================================

import { useState } from 'react';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { useFlows } from '@/hooks/useFlows';
import { formatPercent, formatShortTime, scoreColor } from '@/lib/socUi';
import type { FlowsFilters } from '@/services/flowsService';

const SORTS: Array<{ key: NonNullable<FlowsFilters['sort']>; label: string }> = [
  { key: 'ts', label: 'newest' },
  { key: 'suspicion', label: 'suspicion' },
  { key: 'bytes', label: 'bytes' },
  { key: 'packets', label: 'packets' },
];

export default function FlowsPage() {
  const { rows, total, isLoading, error, reload } = useFlows();
  const [q, setQ] = useState('');
  const [sort, setSort] = useState<NonNullable<FlowsFilters['sort']>>('ts');
  const [minSuspicion, setMinSuspicion] = useState(0);

  const applyFilters = () => {
    void reload({
      q: q || undefined,
      minSuspicion: minSuspicion > 0 ? minSuspicion : undefined,
      sort,
    });
  };

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <GlassCard className="flex flex-wrap items-center gap-3">
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="host search..."
          className="min-w-[200px] rounded border border-outline/70 bg-elevated px-3 py-[7px] text-sm text-ink outline-none transition placeholder:text-[rgb(var(--lated-faint))] focus:border-cyan/60"
        />

        <label className="flex items-center gap-2 text-[11px] text-[rgb(var(--lated-muted))]">
          min suspicion
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minSuspicion}
            onChange={(event) => setMinSuspicion(parseFloat(event.target.value))}
            className="accent-cyan"
          />
          <span className="font-mono text-cyan">{minSuspicion.toFixed(2)}</span>
        </label>

        <div className="flex items-center gap-1.5 text-[11px]">
          <span className="text-[rgb(var(--lated-muted))]">sort</span>
          {SORTS.map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => setSort(option.key)}
              className="rounded border px-[9px] py-1 text-[11px] transition"
              style={{
                borderColor: sort === option.key ? 'rgb(var(--lated-cyan) / 0.6)' : 'rgb(var(--lated-outline))',
                color: sort === option.key ? 'rgb(var(--lated-cyan))' : 'rgb(var(--lated-muted))',
                background: sort === option.key ? 'rgb(var(--lated-cyan) / 0.12)' : 'transparent',
              }}
            >
              {option.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={applyFilters}
          className="ml-auto rounded border border-cyan/60 bg-cyan/10 px-3 py-1.5 text-xs text-cyan transition hover:bg-cyan/20"
        >
          apply
        </button>

        <span className="text-[11px] text-[rgb(var(--lated-muted))]">{rows.length}/{total}</span>
      </GlassCard>

      <GlassCard className="flex-1 overflow-y-auto">
        {isLoading && <p className="text-sm text-[rgb(var(--lated-muted))]">loading flows...</p>}
        {error && <p className="text-sm text-rose-300">{error}</p>}
        {!isLoading && rows.length === 0 && <p className="text-sm text-[rgb(var(--lated-muted))]">No flows match the current filters.</p>}

        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-[0.06em] text-[rgb(var(--lated-muted))]">
              <th className="px-1 py-2">ts</th>
              <th className="px-1 py-2">src</th>
              <th className="px-1 py-2">dst</th>
              <th className="px-1 py-2">proto</th>
              <th className="px-1 py-2 text-right">bytes</th>
              <th className="px-1 py-2 text-right">packets</th>
              <th className="px-1 py-2 text-right">suspicion</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((flow) => (
              <tr key={flow.flow_id} className="border-t border-outline/70">
                <td className="whitespace-nowrap px-1 py-1.5 text-[11px] text-[rgb(var(--lated-muted))]">{formatShortTime(flow.ts)}</td>
                <td className="px-1 py-1.5 font-mono text-[11px] text-ink">{flow.src_host}:{flow.src_port}</td>
                <td className="px-1 py-1.5 font-mono text-[11px] text-ink">{flow.dst_host}:{flow.dst_port}</td>
                <td className="px-1 py-1.5"><NeonBadge tone="muted">{flow.protocol}</NeonBadge></td>
                <td className="px-1 py-1.5 text-right font-mono">{flow.byte_count.toLocaleString()}</td>
                <td className="px-1 py-1.5 text-right font-mono">{flow.packet_count}</td>
                <td className="px-1 py-1.5 text-right font-mono" style={{ color: scoreColor(flow.suspicion) }}>
                  {formatPercent(flow.suspicion)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>
    </div>
  );
}
