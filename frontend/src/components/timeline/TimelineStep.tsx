// =============================================================================
// components/timeline/TimelineStep.tsx
// =============================================================================
//
// ROLE
// ----
// One step in the AttackTimeline. Shows:
//   - step number, kind (recon/pivot/lm), timestamp,
//   - subject host -> target hosts arrow,
//   - linked alert ids (chips),
//   - MITRE tags (small pills).
//
// VISUAL LANGUAGE
// ---------------
//   - Recon: violet accent.
//   - Pivot: cyan accent.
//   - LM   : neon accent + `pulseGlow` while the step is "live".
// =============================================================================

export function TimelineStep() {
  return <div className="border-l-2 pl-4 py-3">{/* step details */}</div>;
}
