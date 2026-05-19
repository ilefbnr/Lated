// =============================================================================
// components/flows/FlowFilters.tsx
// =============================================================================
//
// ROLE
// ----
// Toolbar of filters above the FlowsTable: free-text search, protocol,
// suspicion threshold, time range, sort.
//
// IMPL NOTES
// ----------
//   - All filters write to uiStore.flowsFilters.
//   - FlowsTable subscribes and re-fetches when filters change (debounced
//     300ms for free-text search).
// =============================================================================

export function FlowFilters() {
  return (
    <div className="glass p-3 flex items-center gap-2">
      {/* search + protocol + suspicion + time range + sort */}
    </div>
  );
}
