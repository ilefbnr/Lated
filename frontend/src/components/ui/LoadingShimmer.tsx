// =============================================================================
// components/ui/LoadingShimmer.tsx
// =============================================================================
//
// ROLE
// ----
// Skeleton placeholder for any panel waiting on data. Uses a diagonal
// gradient sweep animation (the Tailwind `scan` keyframe) for cyber feel.
// =============================================================================

import clsx from 'clsx';

export function LoadingShimmer({ className }: { className?: string }) {
  return (
    <div className={clsx('relative overflow-hidden bg-elevated/40 rounded-xl', className)}>
      <div className="absolute inset-x-0 -inset-y-1/2 animate-scan
                      bg-gradient-to-b from-transparent via-cyan/10 to-transparent" />
    </div>
  );
}
