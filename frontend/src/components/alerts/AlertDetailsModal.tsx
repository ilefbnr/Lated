// =============================================================================
// components/alerts/AlertDetailsModal.tsx
// =============================================================================
//
// ROLE
// ----
// Full-detail modal for a selected alert. Tabs:
//   1. Summary       — narrative + severity + host + score
//   2. Explainability — TGNN attention map + recon signals + history
//   3. Evidence      — canonical flow ids with quick-jump to /flows
//   4. MITRE         — tactics + techniques + linked references
//   5. Actions       — acknowledge, close (with disposition), suppress
//
// DATA
// ----
//   - Opened with the alert from the store.
//   - Lazy-loads richer evidence via alertsService.detail(alert_id).
//
// CYBERSECURITY UX REASONING
// --------------------------
// Explainability tab is mandatory — without it analysts cannot defend the
// dispositions to incident commanders. The flow ids on the Evidence tab
// are deep-linked into /flows for one-click pivot.
// =============================================================================

export function AlertDetailsModal() {
  return null; // architecture skeleton
}
