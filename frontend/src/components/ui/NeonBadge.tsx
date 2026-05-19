// =============================================================================
// components/ui/NeonBadge.tsx
// =============================================================================
//
// ROLE
// ----
// Compact pill used for tags (MITRE, protocol, status). Cyan-themed by
// default; supports `tone` overrides.
// =============================================================================

import clsx from 'clsx';

export interface NeonBadgeProps {
  children: React.ReactNode;
  tone?: 'cyan' | 'violet' | 'muted';
}

export function NeonBadge({ children, tone = 'cyan' }: NeonBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider rounded-full border',
        tone === 'cyan'   && 'border-cyan/60   text-cyan   bg-cyan/10',
        tone === 'violet' && 'border-violet/60 text-violet bg-violet/10',
        tone === 'muted'  && 'border-outline   text-muted',
      )}
    >
      {children}
    </span>
  );
}
