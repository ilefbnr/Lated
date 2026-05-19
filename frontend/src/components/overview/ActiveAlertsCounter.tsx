// =============================================================================
// components/overview/ActiveAlertsCounter.tsx
// =============================================================================
//
// ROLE
// ----
// Pulsing big-number tile showing the current count of OPEN alerts. Splits
// the count by severity (critical / high / medium / low) underneath.
//
// DATA
// ----
// Reads from `alertsStore.openCounts`. The store is hydrated by:
//   - alertsService.summary() on mount,
//   - WebSocket EVT_ALERT_NEW / EVT_ALERT_UPDATE.
//
// VISUAL LANGUAGE
// ---------------
//   - Tile uses `.glass` panel.
//   - Number rendered in JetBrains Mono for that "telemetry" feel.
//   - Critical count triggers `pulseGlow` Framer variant when > 0.
//
// CYBERSECURITY UX REASONING
// --------------------------
// This is the single most-watched element in a SOC dashboard. It MUST
// reflect ground truth: no client-side optimistic counters, no debouncing
// past 250ms. When the number changes, it changes immediately.
// =============================================================================

export function ActiveAlertsCounter() {
  // const counts = useAlertsStore(s => s.openCounts);
  return (
    <div className="glass p-5 h-full flex flex-col gap-3">
      <p className="section-title">Active Alerts</p>
      {/* big mono number + per-severity strip */}
    </div>
  );
}
