// =============================================================================
// components/graph/PathHighlighter.tsx
// =============================================================================
//
// ROLE
// ----
// SVG overlay on top of the Cytoscape canvas that draws ANIMATED attack
// paths using D3 + Framer Motion `pathDraw` variants. Edges grow from
// source to target, conveying a sense of attacker propagation.
//
// DATA
// ----
//   - pathsStore.activePaths.
//
// IMPL NOTES
// ----------
//   - The overlay is absolutely positioned over the Cytoscape container.
//   - Each path is rendered as a polyline through the Cytoscape positions
//     of its hosts; positions are synced via cy events.
// =============================================================================

export function PathHighlighter() {
  return null; // architecture skeleton
}
