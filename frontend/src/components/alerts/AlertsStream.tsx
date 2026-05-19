// =============================================================================
// components/alerts/AlertsStream.tsx
// =============================================================================
//
// ROLE
// ----
// Virtualized, append-on-top list of <AlertCard>. Powers the live alert
// triage experience on /alerts.
//
// DATA
// ----
//   - alertsStore.list (sorted by created_at desc).
//   - subscribes to alertsStream via useAlertsStream().
//
// PERFORMANCE
// -----------
//   - Virtualization keeps DOM small even with thousands of alerts in store.
//   - New alert insertion uses Framer Motion `fadeUp` for a subtle entrance.
// =============================================================================

export function AlertsStream() {
  return (
    <div className="glass flex-1 overflow-hidden">
      {/* virtualized list of AlertCard */}
    </div>
  );
}
