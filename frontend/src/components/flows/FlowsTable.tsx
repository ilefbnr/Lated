// =============================================================================
// components/flows/FlowsTable.tsx
// =============================================================================
//
// ROLE
// ----
// Virtualized, searchable, sortable table of suspicious flows.
// Columns: ts, src_host, dst_host, src_port, dst_port, proto, bytes,
//          packets, suspicion, related_alert_id.
//
// DATA
// ----
//   - flowsStore.list (hydrated via flowsService).
//   - Throttled live updates from WS `flows` channel (flush every 1s).
//
// PERFORMANCE
// -----------
//   - Virtualization is non-optional; flow volume can be very high.
//   - Sorting is server-side (sort=... query param) — never client-side
//     across millions of rows.
// =============================================================================

export function FlowsTable() {
  return (
    <div className="glass flex-1 overflow-hidden">
      {/* virtualized rows */}
    </div>
  );
}
