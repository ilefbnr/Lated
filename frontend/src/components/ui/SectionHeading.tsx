import type { ReactNode } from 'react';
import clsx from 'clsx';

export interface SectionHeadingProps {
  children: ReactNode;
  className?: string;
  accent?: 'violet' | 'cyan' | 'rose';
}

export function SectionHeading({ children, className, accent = 'violet' }: SectionHeadingProps) {
  return (
    <p
      className={clsx(
        'border-l-2 pl-3 text-[11px] font-medium uppercase tracking-[0.24em] text-muted',
        accent === 'violet' && 'border-violet/60',
        accent === 'cyan' && 'border-cyan/60',
        accent === 'rose' && 'border-rose-400/60',
        className,
      )}
    >
      {children}
    </p>
  );
}
