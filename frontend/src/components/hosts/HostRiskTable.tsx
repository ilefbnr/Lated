// =============================================================================
// components/hosts/HostRiskTable.tsx
// =============================================================================
//
// ROLE
// ----
// Main table for the /hosts page. Sortable + filterable list of all hosts
// with current decayed risk, active alert count, subnet, and last activity.
//
// DATA
// ----
//   - hostsStore.list, with sort/filter state in uiStore.
//
// IMPL NOTES
// ----------
//   - Virtualized (large environments may exceed 50k hosts).
//   - Clicking a row sets `selectedHostId` in uiStore — drives the right
//     column (profile + risk evolution + heatmap).
// =============================================================================

export function HostRiskTable() {
  return (
    <div className="glass h-full">
      {/* virtualized table */}
    </div>
  );
}
