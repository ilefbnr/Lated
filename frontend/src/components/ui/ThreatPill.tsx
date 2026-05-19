// =============================================================================
// components/ui/ThreatPill.tsx
// =============================================================================
//
// ROLE
// ----
// Severity-colored pill used wherever an Alert/Path severity is shown.
// Uses the palette.sev tokens for color consistency with the rest of the UI.
// =============================================================================

import type { Severity } from '@/types/alerts';
import { severityColor } from '@/themes/tokens';

export interface ThreatPillProps {
  severity: Severity;
}

export function ThreatPill({ severity }: ThreatPillProps) {
  const color = severityColor(severity);
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider rounded-full"
      style={{
        color,
        borderColor: color,
        borderWidth: 1,
        backgroundColor: `${color}1A`, // 10% alpha
      }}
    >
      {severity}
    </span>
  );
}
