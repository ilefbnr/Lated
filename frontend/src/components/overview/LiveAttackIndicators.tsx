// =============================================================================
// components/overview/LiveAttackIndicators.tsx
// =============================================================================
//
// ROLE
// ----
// Horizontal strip of animated tiles, one per IN-PROGRESS AttackPath.
// Each tile shows: pivot host, current step, age, predicted next target.
//
// DATA
// ----
//   - pathsStore.activePaths
//   - WebSocket `paths` channel updates.
//
// VISUAL LANGUAGE
// ---------------
//   - Tiles tinted by severity, ringed with neon halo via `pulseGlow`.
//   - Hover lifts the tile + reveals "Open in Attack Graph" CTA.
//
// CYBERSECURITY UX REASONING
// --------------------------
// Active paths are higher priority than individual alerts — they represent
// confirmed multi-step incidents. Surfacing them front-and-center accelerates
// MTTR (mean time to remediate).
// =============================================================================

export function LiveAttackIndicators() {
  return (
    <div className="glass p-5 h-full">
      <p className="section-title mb-4">Active Attack Paths</p>
      {/* horizontal scroll of motion-cards */}
    </div>
  );
}
