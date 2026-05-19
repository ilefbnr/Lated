// =============================================================================
// components/graph/GraphControls.tsx
// =============================================================================
//
// ROLE
// ----
// Floating control panel anchored to the top-right of the attack-graph
// canvas. Provides:
//   - zoom in / out / fit-to-screen,
//   - layout reset,
//   - filter (subnet, severity threshold, hide-benign-nodes toggle),
//   - timeline scrubber (replay last N minutes).
//
// IMPL NOTES
// ----------
//   - Controls dispatch to graphStore via Zustand actions; the canvas
//     subscribes and mutates Cytoscape state in response (one-way data flow).
// =============================================================================

export function GraphControls() {
  return (
    <div className="absolute top-4 right-4 glass p-3 flex flex-col gap-2 z-10">
      {/* zoom / fit / replay / filters */}
    </div>
  );
}
