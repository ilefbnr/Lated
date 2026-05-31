import clsx from 'clsx';
import { MoonIcon, SunIcon } from 'lucide-react';

import { useUIStore } from '@/stores/uiStore';

export interface ThemeToggleButtonProps {
  className?: string;
}

export function ThemeToggleButton({ className }: ThemeToggleButtonProps) {
  const theme = useUIStore((state) => state.theme);
  const toggleTheme = useUIStore((state) => state.toggleTheme);

  return (
    <button
      type="button"
      onClick={toggleTheme}
      title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
      className={clsx(
        'inline-flex h-9 w-9 items-center justify-center rounded-full border border-outline bg-elevated/80 text-ink transition',
        'hover:border-brand/60 hover:text-brand',
        className,
      )}
    >
      {theme === 'dark' ? <SunIcon size={15} /> : <MoonIcon size={15} />}
    </button>
  );
}
