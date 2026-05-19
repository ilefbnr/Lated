// =============================================================================
// layouts/TopBar.tsx — top command bar
// =============================================================================

import { useRouter } from 'next/router';
import clsx from 'clsx';

import { useUIStore } from '@/stores/uiStore';
import { useUserStore } from '@/stores/userStore';

export function TopBar() {
  const router = useRouter();
  const wsConnected = useUIStore((state) => state.wsConnected);
  const env = useUIStore((state) => state.env);
  const user = useUserStore((state) => state.user);
  const logout = useUserStore((state) => state.logout);

  const handleLogout = () => {
    logout();
    void router.replace('/login');
  };

  return (
    <header className="h-16 flex items-center justify-between px-6 m-3 mb-0 glass">
      <div className="flex items-center gap-4 text-sm">
        <span className="text-muted">Console</span>
        <span className="text-ink font-medium">LateD SOC</span>
      </div>
      <div className="flex items-center gap-3">
        <span
          className={clsx(
            'inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider rounded-full border',
            env === 'production'
              ? 'border-rose-400/60 text-rose-300 bg-rose-400/10'
              : env === 'staging'
                ? 'border-amber-400/60 text-amber-300 bg-amber-400/10'
                : 'border-cyan/60 text-cyan bg-cyan/10',
          )}
        >
          {env}
        </span>
        <span
          className={clsx(
            'inline-flex items-center gap-2 text-xs px-2 py-1 rounded-full border',
            wsConnected
              ? 'border-emerald-400/60 text-emerald-300 bg-emerald-400/10'
              : 'border-rose-400/60 text-rose-300 bg-rose-400/10',
          )}
          aria-live="polite"
        >
          <span
            className={clsx(
              'w-2 h-2 rounded-full',
              wsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400',
            )}
          />
          {wsConnected ? 'live' : 'offline'}
        </span>
        {user !== null && (
          <div className="flex items-center gap-2 pl-3 border-l border-outline/40">
            <div className="text-right">
              <p className="text-xs text-ink font-mono leading-tight">{user.username}</p>
              <p
                className={clsx(
                  'text-[10px] uppercase tracking-wider leading-tight',
                  user.role === 'admin'
                    ? 'text-violet'
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
              className="text-[11px] text-muted hover:text-ink border border-outline/60 hover:border-cyan/60 rounded px-2 py-1"
            >
              sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
