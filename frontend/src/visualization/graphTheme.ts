// =============================================================================
// visualization/graphTheme.ts — risk-to-color mapping for the graph
// =============================================================================
// Pure functions. Kept separate from cytoscapeConfig to allow reuse from
// the D3 overlays (PathHighlighter, heatmap).
// =============================================================================

import { palette } from '@/themes/tokens';

export function riskColor(risk: number): string {
  if (risk >= 0.90) return palette.sev.critical;
  if (risk >= 0.75) return palette.sev.high;
  if (risk >= 0.60) return palette.sev.medium;
  if (risk >= 0.40) return palette.sev.low;
  return palette.sev.info;
}

export function edgeOpacity(weight: number): number {
  // weight in [0, 1] -> opacity in [0.15, 1]
  return 0.15 + 0.85 * Math.max(0, Math.min(1, weight));
}
