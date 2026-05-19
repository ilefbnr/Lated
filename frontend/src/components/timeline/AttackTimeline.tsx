// =============================================================================
// components/timeline/AttackTimeline.tsx
// =============================================================================
//
// ROLE
// ----
// Vertical stepper visualizing the Recon -> LM sequence of an AttackPath.
// Each step is a <TimelineStep>. The vertical rail is a gradient
// (recon: violet, lm: cyan) that pulses while the path is still evolving.
//
// DATA
// ----
//   - pathsService.timeline(path_id), live updates via WS `timeline` channel.
// =============================================================================

export function AttackTimeline() {
  return (
    <div className="glass p-5 flex-1 overflow-y-auto">
      {/* stepper */}
    </div>
  );
}
