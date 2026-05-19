// =============================================================================
// components/timeline/PhaseIndicator.tsx
// =============================================================================
//
// ROLE
// ----
// Three-segment progress bar (Recon | Pivot | LM) showing which phase the
// currently-selected AttackPath is in. The active segment animates.
//
// CYBERSECURITY UX REASONING
// --------------------------
// Phase awareness drives response prioritization. A path still in "Recon"
// is far less urgent than one already in "LM". Surfacing the phase at the
// top of the timeline page sets expectations immediately.
// =============================================================================

export function PhaseIndicator() {
  return (
    <div className="glass p-3 flex items-center gap-3">
      {/* three-segment bar */}
    </div>
  );
}
