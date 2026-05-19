// =============================================================================
// components/overview/ThreatSeverityWidget.tsx
// =============================================================================
//
// ROLE
// ----
// Donut chart breakdown of currently open alerts by severity. Center label
// shows the dominant severity ("HIGH"), small numbers per slice.
//
// DATA
// ----
//   - alertsStore.openCounts (same data feed as ActiveAlertsCounter).
//
// IMPL NOTES
// ----------
// Rendered with D3 (arc + pie) inside a small SVG. We avoid charting
// libraries to keep the bundle lean and the visuals exactly on-brand.
// =============================================================================

export function ThreatSeverityWidget() {
  return (
    <div className="glass p-5 h-full flex flex-col">
      <p className="section-title">Severity Distribution</p>
      {/* D3 donut */}
    </div>
  );
}
