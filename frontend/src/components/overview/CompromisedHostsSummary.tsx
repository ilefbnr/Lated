// =============================================================================
// components/overview/CompromisedHostsSummary.tsx
// =============================================================================
//
// ROLE
// ----
// Shortlist of top-N hosts by current decayed risk, with one-click
// drill-down into the host profile (navigates to /hosts?host_id=...).
//
// DATA
// ----
//   - hostsStore.topRisky (hydrated by hostsService.topRisky()).
//
// VISUAL LANGUAGE
// ---------------
//   - Compact rows with mono-text host_id, hostname, severity badge.
//   - Each row's right edge shows a thin <RiskMiniBar>.
// =============================================================================

export function CompromisedHostsSummary() {
  return (
    <div className="glass p-5 h-full flex flex-col gap-3">
      <p className="section-title">Top Risky Hosts</p>
      {/* list of rows */}
    </div>
  );
}
