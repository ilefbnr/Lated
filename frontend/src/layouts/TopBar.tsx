// =============================================================================
// layouts/TopBar.tsx — top command bar with theme toggle
// =============================================================================

import { useRouter } from 'next/router';
import clsx from 'clsx';

import { ThemeToggleButton } from '@/components/ui/ThemeToggleButton';
import { useUIStore } from '@/stores/uiStore';
import { useUserStore } from '@/stores/userStore';

export function TopBar() {
  const router = useRouter();
  const wsConnected = useUIStore((state) => state.wsConnected);
  const env = useUIStore((state) => state.env);
  const user = useUserStore((state) => state.user);
  const logout = useUserStore((state) => state.logout);
  const envLabel = env === 'development' ? 'dev' : env;

  const handleLogout = () => {
    logout();
    void router.replace('/login');
  };

  return (
    <header className="glass m-3 mb-0 flex h-[60px] items-center justify-between px-[22px]">
      <div className="flex items-center gap-4 text-[13px]">
        <span className="text-[rgb(var(--lated-muted))]">Console</span>
        <span className="font-medium text-[rgb(var(--lated-ink))]">LateD SOC</span>
        <span
          className={clsx(
            'ml-1 inline-flex rounded-full border px-[9px] py-[1px] text-[10px] uppercase tracking-[0.06em]',
            env === 'production'
              ? 'border-rose-400/60 bg-rose-400/10 text-rose-300'
              : env === 'staging'
                ? 'border-amber-400/60 bg-amber-400/10 text-amber-300'
                : 'border-cyan/60 bg-cyan/10 text-cyan',
          )}
        >
          {envLabel}
        </span>
      </div>

      <div className="flex items-center gap-3">
        <span
          className={clsx(
            'inline-flex items-center gap-2 rounded-full border px-2 py-1 text-xs',
            wsConnected
              ? 'border-emerald-400/60 bg-emerald-400/10 text-emerald-300'
              : 'border-rose-400/60 bg-rose-400/10 text-rose-300',
          )}
          aria-live="polite"
        >
          <span
            className={clsx(
              'lated-anim-pulse-dot h-[7px] w-[7px] rounded-full',
              wsConnected ? 'bg-emerald-400' : 'bg-rose-400',
            )}
          />
          {wsConnected ? 'live' : 'offline'}
        </span>

        <ThemeToggleButton />

        {user !== null && (
          <div className="flex items-center gap-[10px] border-l border-outline/70 pl-[14px]">
            <div className="text-right">
              <p className="text-xs leading-tight text-[rgb(var(--lated-ink))] font-mono">{user.username}</p>
              <p
                className={clsx(
                  'text-[10px] uppercase tracking-wider leading-tight',
                  user.role === 'admin'
                    ? 'text-brand'
                    : user.role === 'supervisor'
                      ? 'text-amber-300'
                      : 'text-cyan',
                )}
              >
                {user.role}
              </p>
            </div>
            <button
              onClick={handleLogout}
              className="rounded border border-outline/70 bg-transparent px-[9px] py-[3px] text-[11px] text-[rgb(var(--lated-muted))] transition hover:border-brand/60 hover:text-[rgb(var(--lated-ink))]"
            >
              sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
