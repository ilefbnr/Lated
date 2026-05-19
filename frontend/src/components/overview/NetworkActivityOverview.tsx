// =============================================================================
// components/overview/NetworkActivityOverview.tsx
// =============================================================================
//
// ROLE
// ----
// Wide panel showing:
//   - flows/sec sparkline (last 60 minutes, 1-minute buckets),
//   - top talkers (by bytes and by suspicion).
//
// DATA
// ----
//   - hostsStore.networkActivity (rolling buffer in the store).
//
// VISUAL LANGUAGE
// ---------------
//   - Sparkline drawn with D3, cyan stroke, area fill at 8% opacity.
//   - Top-talker rows include a thin animated "scan" gradient on hover.
// =============================================================================

export function NetworkActivityOverview() {
  return (
    <div className="glass p-5 h-full">
      <p className="section-title mb-3">Network Activity</p>
      {/* sparkline + top-talker list */}
    </div>
  );
}
