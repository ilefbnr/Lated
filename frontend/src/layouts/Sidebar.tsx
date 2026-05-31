// =============================================================================
// layouts/Sidebar.tsx — primary navigation
// =============================================================================

import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/router';
import clsx from 'clsx';
import {
  BellIcon,
  ClockIcon,
  GithubIcon,
  ListIcon,
  NetworkIcon,
  RadarIcon,
  ServerIcon,
  SettingsIcon,
  ShieldAlertIcon,
} from 'lucide-react';

import type { Role } from '@/services/authService';
import { useUserStore } from '@/stores/userStore';

interface NavItem {
  href: string;
  label: string;
  icon: typeof ShieldAlertIcon;
  minRole?: Role;
}

const items: NavItem[] = [
  { href: '/overview', label: 'Overview', icon: ShieldAlertIcon },
  { href: '/discovery', label: 'Discovery', icon: RadarIcon },
  { href: '/alerts', label: 'Alerts', icon: BellIcon },
  { href: '/attack-graph', label: 'Attack Graph', icon: NetworkIcon },
  { href: '/hosts', label: 'Hosts', icon: ServerIcon },
  { href: '/timeline', label: 'Timeline', icon: ClockIcon },
  { href: '/flows', label: 'Flows', icon: ListIcon },
  { href: '/admin', label: 'Admin', icon: SettingsIcon, minRole: 'admin' },
];

export function Sidebar() {
  const router = useRouter();
  const hasRole = useUserStore((state) => state.hasRole);

  return (
    <aside className="glass m-3 mr-0 flex w-[232px] shrink-0 flex-col gap-1 p-4" aria-label="Primary">
      <div className="mb-[18px] flex items-center gap-3 px-2 py-[6px]">
        <span className="lated-logo-halo inline-flex h-[38px] w-[38px] items-center justify-center rounded-2xl shadow-[0_10px_28px_rgba(139,107,240,0.35)]">
          <Image src="/logo.png" alt="LateD logo" width={38} height={38} className="h-[38px] w-[38px] object-contain" priority />
        </span>
        <div>
          <p className="m-0 text-[10px] font-semibold uppercase tracking-[0.3em] text-[rgb(var(--lated-muted))]">LATED</p>
          <p className="m-0 whitespace-nowrap font-display text-sm font-semibold leading-tight text-[rgb(var(--lated-ink))]">SOC Command</p>
        </div>
      </div>

      {items.map((item) => {
        if (item.minRole !== undefined && !hasRole(item.minRole)) return null;
        const active = router.pathname === item.href;
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            className={clsx(
              'relative flex items-center gap-[11px] rounded-lg border px-3 py-[9px] text-[13px] transition-all',
              active
                ? 'border-brand/45 bg-brand/10 text-brand'
                : 'border-transparent text-[rgb(var(--lated-muted))] hover:bg-[rgb(var(--lated-elevated))] hover:text-[rgb(var(--lated-ink))]',
            )}
          >
            {active && <span className="absolute inset-y-[6px] left-0 w-[3px] rounded-full bg-[var(--lated-grad-brand)]" />}
            <Icon size={15} />
            <span>{item.label}</span>
          </Link>
        );
      })}

      <a
        href="https://github.com/ilefbnr/Lated"
        target="_blank"
        rel="noreferrer"
        className="mt-auto flex items-center gap-2 border-t border-outline/70 px-[10px] pt-[14px] text-[11px] text-[rgb(var(--lated-muted))] transition hover:text-[rgb(var(--lated-ink))]"
      >
        <GithubIcon size={13} />
        <span>github.com/ilefbnr/Lated</span>
      </a>
    </aside>
  );
}
