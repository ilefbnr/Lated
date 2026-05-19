// =============================================================================
// components/alerts/SeverityFilter.tsx
// =============================================================================
//
// ROLE
// ----
// Top toolbar chips for filtering the alert stream by severity. Each chip
// also shows the count for its severity.
//
// VISUAL LANGUAGE
// ---------------
//   - Selected chip pulses with `pulseGlow`.
//   - Unselected chips are dimmed but still readable (telemetry feel).
// =============================================================================

export function SeverityFilter() {
  return (
    <div className="flex items-center gap-2">
      {/* one chip per severity, mapped through severityColor() */}
    </div>
  );
}
