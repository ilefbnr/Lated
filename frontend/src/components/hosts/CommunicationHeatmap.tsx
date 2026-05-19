// =============================================================================
// components/hosts/CommunicationHeatmap.tsx
// =============================================================================
//
// ROLE
// ----
// Heatmap of communication intensity between the selected host and its
// top-K neighbors. Brighter cells = higher byte volume; red overlay = high
// suspicion.
//
// IMPL NOTES
// ----------
//   - Uses src/visualization/d3Heatmap.ts.
//   - Hover reveals exact (bytes, packets, suspicion) tuples.
// =============================================================================

export function CommunicationHeatmap() {
  return <div className="glass p-5 h-64">{/* D3 heatmap */}</div>;
}
