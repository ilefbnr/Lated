// =============================================================================
// components/flows/FlowRow.tsx
// =============================================================================
//
// ROLE
// ----
// One row of the FlowsTable. Expandable on click to reveal full
// CanonicalFlow + detection metadata + a "view in attack graph" CTA.
//
// VISUAL LANGUAGE
// ---------------
//   - Mono-text for ports, host_ids, hashes.
//   - A thin colored bar on the right encodes suspicion (severity gradient).
// =============================================================================

export function FlowRow() {
  return <div className="border-b border-outline/50 px-4 py-2">{/* row */}</div>;
}
