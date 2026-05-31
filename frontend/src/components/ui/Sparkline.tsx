export interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

export function Sparkline({
  data,
  width = 320,
  height = 70,
  color = 'rgb(var(--lated-cyan) / 1)',
}: SparklineProps) {
  if (data.length === 0) {
    return <div className="h-[70px] rounded-xl bg-elevated/40" />;
  }

  const max = Math.max(...data, 1);
  const step = data.length > 1 ? width / (data.length - 1) : width;
  const points = data
    .map((value, index) => `${index * step},${height - (value / max) * (height - 6) - 3}`)
    .join(' ');
  const area = `M 0 ${height} L ${points} L ${width} ${height} Z`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="block h-auto w-full">
      <path d={area} fill={color} opacity="0.08" />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}
