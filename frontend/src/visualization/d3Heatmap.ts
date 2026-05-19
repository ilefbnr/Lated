// =============================================================================
// visualization/d3Heatmap.ts — D3 heatmap renderer
// =============================================================================
//
// PURPOSE
// -------
// Renders the host CommunicationHeatmap. Decoupled from React so the
// component just mounts an svg and calls renderHeatmap(svgEl, data).
//
// API
// ---
//   renderHeatmap(svgEl: SVGSVGElement, cells: HostHeatmapCell[]): void
//
// COLOR ENCODING
// --------------
//   intensity -> cyan ramp
//   suspicion -> rose overlay (alpha-blended)
// =============================================================================

import type { HostHeatmapCell } from '@/types/hosts';

export function renderHeatmap(_svg: SVGSVGElement, _cells: HostHeatmapCell[]): void {
  // architecture skeleton
}
