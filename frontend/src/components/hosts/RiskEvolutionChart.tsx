// =============================================================================
// components/hosts/RiskEvolutionChart.tsx
// =============================================================================
//
// ROLE
// ----
// D3-rendered line chart of the selected host's risk over the last 24h.
// Highlights alert timestamps as vertical markers along the curve.
//
// CYBERSECURITY UX REASONING
// --------------------------
// Risk evolution gives temporal context to an alert: "was this host
// already trending up for an hour, or did this come from nowhere?"
// Sudden spikes warrant different triage than slow climbs.
// =============================================================================

export function RiskEvolutionChart() {
  return <div className="glass p-5 h-48">{/* D3 line chart */}</div>;
}
