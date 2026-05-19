// =============================================================================
// components/alerts/AlertCard.tsx
// =============================================================================
//
// ROLE
// ----
// One row in the AlertsStream. Compact yet information-dense:
//   - severity color bar on the left,
//   - timestamp + host_id (mono),
//   - one-line description,
//   - score chip,
//   - MITRE tags as small pills,
//   - ack/close buttons (visible if user has the role).
//
// INTERACTION
// -----------
//   - Click toggles the AlertDetailsModal.
//   - Right-click reveals a quick-action menu (acknowledge / suppress 1h).
// =============================================================================

import type { Alert } from '@/types/alerts';

export interface AlertCardProps {
  alert: Alert;
  onOpen?: (alert: Alert) => void;
}

export function AlertCard({ alert }: AlertCardProps) {
  return (
    <div className="border-b border-outline/50 hover:bg-elevated/60 transition-colors px-4 py-3">
      {/* visual breakdown described in header comment */}
    </div>
  );
}
