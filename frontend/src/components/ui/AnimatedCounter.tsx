// =============================================================================
// components/ui/AnimatedCounter.tsx
// =============================================================================
//
// ROLE
// ----
// Numeric counter that tweens to its new value over ~300ms. Used by the
// overview counters so changes feel "alive" rather than snap-replacing.
//
// PROPS
// -----
//   value       : target number.
//   durationMs  : tween duration (default 300).
//
// IMPL NOTES
// ----------
//   Real implementation uses Framer Motion's animate() or motionValue.
// =============================================================================

export interface AnimatedCounterProps {
  value: number;
  durationMs?: number;
}

export function AnimatedCounter({ value }: AnimatedCounterProps) {
  return <span className="mono-val text-3xl">{value}</span>;
}
