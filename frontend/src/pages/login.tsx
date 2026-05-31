// =============================================================================
// pages/login.tsx — hero login screen with full-bleed brand treatment
// =============================================================================

import { useState } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/router';
import clsx from 'clsx';
import {
  ArrowRightIcon,
  EyeIcon,
  MoonIcon,
  ShieldCheckIcon,
  SunIcon,
  UsersIcon,
} from 'lucide-react';

import { GlassCard } from '@/components/ui/GlassCard';
import { useUIStore } from '@/stores/uiStore';
import { useUserStore } from '@/stores/userStore';
import type { Role } from '@/services/authService';

const DEV_TOKENS: Array<{
  role: Role;
  token: string;
  description: string;
  icon: typeof EyeIcon;
  accent: string;
}> = [
  {
    role: 'analyst',
    token: 'analyst-token',
    description: 'Read access + acknowledge alerts.',
    icon: EyeIcon,
    accent: 'from-cyan to-brandBlue',
  },
  {
    role: 'supervisor',
    token: 'supervisor-token',
    description: 'Analyst rights + close alerts with disposition.',
    icon: UsersIcon,
    accent: 'from-amber-400 to-orange-400',
  },
  {
    role: 'admin',
    token: 'admin-token',
    description: 'Supervisor rights + reload thresholds + model swap.',
    icon: ShieldCheckIcon,
    accent: 'from-brandStrong to-brandBlue',
  },
];

const LIVE_METRICS = [
  ['HOSTS PROTECTED', '12,840'],
  ['MTTR', '4.2m'],
  ['ALERTS / DAY', '1.2K'],
  ['UPTIME', '99.99%'],
] as const;

export default function LoginPage() {
  const router = useRouter();
  const login = useUserStore((state) => state.login);
  const loading = useUserStore((state) => state.loading);
  const error = useUserStore((state) => state.error);
  const theme = useUIStore((state) => state.theme);
  const toggleTheme = useUIStore((state) => state.toggleTheme);
  const [customToken, setCustomToken] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [hoverRole, setHoverRole] = useState<Role | null>(null);

  const submitToken = async (token: string) => {
    setBusy(token);
    const user = await login(token);
    setBusy(null);
    if (user !== null) {
      void router.replace('/overview');
    }
  };

  return (
    <div className="relative grid min-h-screen overflow-hidden bg-[rgb(var(--lated-canvas))] text-[rgb(var(--lated-ink))] lg:grid-cols-[1.05fr_1fr]">
      <button
        type="button"
        onClick={toggleTheme}
        title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        className="absolute right-5 top-5 z-10 inline-flex h-10 w-10 items-center justify-center rounded-full border border-outline/70 bg-[var(--lated-glass-bg)] text-[rgb(var(--lated-ink))] backdrop-blur-xl transition hover:border-brand/60 hover:text-brand"
      >
        {theme === 'dark' ? <SunIcon size={16} /> : <MoonIcon size={16} />}
      </button>

      <section className="relative flex flex-col justify-between overflow-hidden px-12 py-12 lg:px-14">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-[-100px]"
          style={{
            background:
              'radial-gradient(600px 600px at 30% 35%, rgb(var(--lated-brand) / 0.4), transparent 60%), radial-gradient(500px 500px at 70% 75%, rgb(var(--lated-violet-blue) / 0.25), transparent 60%)',
            filter: 'blur(20px)',
          }}
        />

        <div className="relative z-[1] flex items-center gap-4">
          <span className="lated-logo-halo inline-flex h-11 w-11 items-center justify-center rounded-2xl shadow-[0_8px_32px_rgba(139,107,240,0.45)]">
            <Image src="/logo.png" alt="LateD logo" width={44} height={44} className="h-11 w-11 object-contain" priority />
          </span>
          <div>
            <p className="m-0 text-[11px] font-semibold uppercase tracking-[0.32em] text-[rgb(var(--lated-muted))]">LATED</p>
            <p className="m-0 text-sm text-[rgb(var(--lated-ink))]">Lateral Movement Detection</p>
          </div>
        </div>

        <div className="relative z-[1] flex flex-col items-start gap-7">
          <div className="lated-logo-halo lated-anim-float inline-flex h-[240px] w-[240px] items-center justify-center rounded-full bg-[radial-gradient(circle_at_50%_45%,rgba(255,255,255,0.16),transparent_62%),var(--lated-grad-brand)] shadow-[0_24px_48px_rgba(139,107,240,0.55)]">
            <Image src="/logo.png" alt="LateD logo" width={240} height={240} className="h-[240px] w-[240px] object-contain" priority />
          </div>

          <div>
            <p className="lated-eyebrow mb-2">SOC Command · v0.4</p>
            <h1 className="lated-hero text-[64px]">
              See the <span className="lated-hero--brand">lateral</span>
              <br />
              before it lands.
            </h1>
            <p className="mt-4 max-w-[460px] text-[15px] leading-[1.55] text-[rgb(var(--lated-muted))]">
              Real-time lateral-movement detection powered by Temporal Graph Neural Networks.
              Attack paths reconstructed in seconds, not hours.
            </p>
          </div>
        </div>

        <div className="relative z-[1] flex flex-wrap gap-8">
          {LIVE_METRICS.map(([label, value]) => (
            <div key={label}>
              <p className="m-0 text-[10px] font-medium uppercase tracking-[0.18em] text-[rgb(var(--lated-muted))]">{label}</p>
              <p className="mt-0.5 font-mono text-[20px] text-[rgb(var(--lated-ink))]">{value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="relative flex items-center justify-center border-l border-outline/70 px-8 py-8">
        <GlassCard className="flex w-full max-w-[420px] flex-col gap-5 p-6">
          <div className="flex flex-col gap-1">
            <p className="text-[10px] uppercase tracking-[0.3em] text-[rgb(var(--lated-muted))]">Authenticate</p>
            <h2 className="font-display text-[26px] font-semibold leading-[1.15] text-[rgb(var(--lated-ink))]">
              Sign in to your <span className="text-brand">console</span>
            </h2>
            <p className="mt-1 text-xs text-[rgb(var(--lated-muted))]">Pick a local role token or paste a bearer/JWT.</p>
          </div>

          <div className="flex flex-col gap-2.5">
            {DEV_TOKENS.map((option) => {
              const Icon = option.icon;
              const isHover = hoverRole === option.role;
              const isBusy = busy === option.token;

              return (
                <button
                  key={option.role}
                  type="button"
                  disabled={loading}
                  onMouseEnter={() => setHoverRole(option.role)}
                  onMouseLeave={() => setHoverRole(null)}
                  onClick={() => void submitToken(option.token)}
                  className={clsx(
                    'flex w-full items-center justify-between gap-3 rounded-xl border px-4 py-3.5 text-left transition-all',
                    isBusy || isHover
                      ? 'border-brand/60 bg-brand/10 shadow-[0_6px_22px_rgba(139,107,240,0.25)] -translate-y-px'
                      : 'border-outline/70 bg-[rgb(var(--lated-elevated))]',
                  )}
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span className={clsx('inline-flex h-[34px] w-[34px] items-center justify-center rounded-lg bg-gradient-to-br text-white', option.accent)}>
                      <Icon size={16} />
                    </span>
                    <div className="min-w-0">
                      <p className="m-0 text-sm font-medium capitalize text-[rgb(var(--lated-ink))]">{option.role}</p>
                      <p className="mt-0.5 text-[11px] text-[rgb(var(--lated-muted))]">{option.description}</p>
                    </div>
                  </div>
                  <ArrowRightIcon size={16} className="shrink-0 text-[rgb(var(--lated-muted))]" />
                </button>
              );
            })}
          </div>

          <div className="flex flex-col gap-2 border-t border-outline/70 pt-4">
            <label className="text-[10px] uppercase tracking-[0.25em] text-[rgb(var(--lated-muted))]">or paste a bearer token</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={customToken}
                onChange={(event) => setCustomToken(event.target.value)}
                placeholder="bearer ..."
                className="flex-1 rounded border border-outline/70 bg-[rgb(var(--lated-elevated))] px-3 py-2 font-mono text-sm text-[rgb(var(--lated-ink))] outline-none transition placeholder:text-[rgb(var(--lated-faint))] focus:border-cyan/60"
              />
              <button
                type="button"
                onClick={() => void submitToken(customToken.trim())}
                disabled={loading || customToken.trim().length === 0}
                className="lated-btn-brand"
              >
                sign in
              </button>
            </div>
          </div>

          {error && <p className="text-xs text-rose-300">{error}</p>}
        </GlassCard>
      </section>
    </div>
  );
}
