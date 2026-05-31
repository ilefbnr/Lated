import { useMemo } from 'react';

import type { Severity } from '@/types/alerts';
import { SEVERITY_COLORS } from '@/lib/socUi';

export interface SeverityDonutProps {
  counts: Record<Severity, number>;
  size?: number;
}

const ORDER: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];

export function SeverityDonut({ counts, size = 100 }: SeverityDonutProps) {
  const total = ORDER.reduce((sum, key) => sum + (counts[key] ?? 0), 0) || 1;
  const radius = size / 2 - 8;
  const center = size / 2;

  const arcs = useMemo(() => {
    let angle = -Math.PI / 2;
    return ORDER.map((key) => {
      const value = counts[key] ?? 0;
      const sweep = (value / total) * Math.PI * 2;
      const startX = center + radius * Math.cos(angle);
      const startY = center + radius * Math.sin(angle);
      const endX = center + radius * Math.cos(angle + sweep);
      const endY = center + radius * Math.sin(angle + sweep);
      const largeArc = sweep > Math.PI ? 1 : 0;
      const path = `M ${startX} ${startY} A ${radius} ${radius} 0 ${largeArc} 1 ${endX} ${endY}`;
      angle += sweep;
      return { key, value, path };
    });
  }, [center, counts, radius, total]);

  const dominant = ORDER.find((key) => (counts[key] ?? 0) > 0) ?? 'info';

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label="Severity distribution">
      <circle cx={center} cy={center} r={radius} fill="none" stroke="rgb(var(--lated-outline) / 1)" strokeWidth="6" />
      {arcs.filter((arc) => arc.value > 0).map((arc) => (
        <path
          key={arc.key}
          d={arc.path}
          fill="none"
          stroke={SEVERITY_COLORS[arc.key]}
          strokeWidth="7"
          strokeLinecap="butt"
        />
      ))}
      <text
        x={center}
        y={center - 2}
        textAnchor="middle"
        fill={SEVERITY_COLORS[dominant]}
        style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: 11,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
        }}
      >
        {dominant}
      </text>
      <text
        x={center}
        y={center + 14}
        textAnchor="middle"
        fill="rgb(var(--lated-muted) / 1)"
        style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}
      >
        {total}
      </text>
    </svg>
  );
}
