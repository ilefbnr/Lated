// =============================================================================
// components/ui/GlassCard.tsx
// =============================================================================
//
// ROLE
// ----
// Reusable glassmorphism container. Every dashboard panel composes from
// this primitive so spacing, blur, and border treatment stay consistent.
//
// PROPS
// -----
//   - elevated   : adds a stronger shadow for "floating" panels.
//   - glow       : applies the cyan glow shadow.
//   - className  : passthrough for layout-specific tweaks.
// =============================================================================

import type { ReactNode } from 'react';
import clsx from 'clsx';

export interface GlassCardProps {
  children: ReactNode;
  elevated?: boolean;
  glow?: boolean;
  className?: string;
}

export function GlassCard({ children, elevated, glow, className }: GlassCardProps) {
  return (
    <div
      className={clsx(
        'glass p-5',
        elevated && 'shadow-panel',
        glow && 'shadow-glow',
        className,
      )}
    >
      {children}
    </div>
  );
}
