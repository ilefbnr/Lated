// =============================================================================
// pages/login.tsx — dev login screen
// =============================================================================
//
// The backend currently ships three pre-registered dev tokens. Operators pick
// the role they want to impersonate; the chosen token is persisted in
// localStorage so refresh keeps the session.
// =============================================================================

import { useState } from 'react';
import { useRouter } from 'next/router';
import clsx from 'clsx';

import { GlassCard } from '@/components/ui/GlassCard';
import { NeonBadge } from '@/components/ui/NeonBadge';
import { useUserStore } from '@/stores/userStore';
import type { Role } from '@/services/authService';

const DEV_TOKENS: Array<{ role: Role; token: string; description: string }> = [
  {
    role: 'analyst',
    token: 'analyst-token',
    description: 'Read access + acknowledge alerts.',
  },
  {
    role: 'supervisor',
    token: 'supervisor-token',
    description: 'Analyst rights + close alerts with disposition.',
  },
  {
    role: 'admin',
    token: 'admin-token',
    description: 'Supervisor rights + reload thresholds + model swap.',
  },
];

export default function LoginPage() {
  const router = useRouter();
  const login = useUserStore((state) => state.login);
  const loading = useUserStore((state) => state.loading);
  const error = useUserStore((state) => state.error);
  const [customToken, setCustomToken] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  const submitToken = async (token: string) => {
    setBusy(token);
    const user = await login(token);
    setBusy(null);
    if (user !== null) {
      void router.replace('/overview');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-canvas text-ink">
      <GlassCard className="w-full max-w-md flex flex-col gap-5" elevated>
        <div className="flex flex-col gap-1">
          <p className="text-[10px] uppercase tracking-[0.3em] text-muted">Authenticate</p>
          <h1 className="text-2xl font-semibold text-cyan">LateD SOC Console</h1>
          <p className="text-xs text-muted">
            Pick a local role token or paste a bearer/JWT token.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          {DEV_TOKENS.map((option) => (
            <button
              key={option.role}
              disabled={loading}
              onClick={() => submitToken(option.token)}
              className={clsx(
                'w-full flex items-start justify-between gap-3 px-4 py-3 rounded border text-left transition-colors',
                'border-outline/60 hover:border-cyan/60 bg-elevated/40 hover:bg-cyan/5',
                busy === option.token && 'border-cyan/60 bg-cyan/10',
              )}
            >
              <div className="min-w-0">
                <p className="text-sm text-ink font-medium capitalize">{option.role}</p>
                <p className="text-[11px] text-muted">{option.description}</p>
              </div>
              <NeonBadge tone={option.role === 'admin' ? 'violet' : 'cyan'}>
                {option.role}
              </NeonBadge>
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-2 border-t border-outline/40 pt-4">
          <label className="text-[10px] uppercase tracking-[0.25em] text-muted">
            or paste a bearer token
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={customToken}
              onChange={(event) => setCustomToken(event.target.value)}
              placeholder="bearer token"
              className="flex-1 bg-elevated/40 border border-outline/60 text-ink text-sm rounded px-3 py-2 focus:outline-none focus:border-cyan/60 font-mono"
            />
            <button
              onClick={() => void submitToken(customToken.trim())}
              disabled={loading || customToken.trim().length === 0}
              className="px-3 py-2 text-xs rounded border border-cyan/60 text-cyan hover:bg-cyan/10 disabled:opacity-40"
            >
              sign in
            </button>
          </div>
        </div>

        {error && <p className="text-xs text-rose-300">{error}</p>}
      </GlassCard>
    </div>
  );
}
