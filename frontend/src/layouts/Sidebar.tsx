// =============================================================================
// layouts/Sidebar.tsx — primary navigation
// =============================================================================

import Link from 'next/link';
import { useRouter } from 'next/router';
import clsx from 'clsx';
import {
  ShieldAlertIcon,
  BellIcon,
  NetworkIcon,
  ServerIcon,
  ClockIcon,
  ListIcon,
  SettingsIcon,
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
  { href: '/overview',     label: 'Overview',     icon: ShieldAlertIcon },
  { href: '/alerts',       label: 'Alerts',       icon: BellIcon },
  { href: '/attack-graph', label: 'Attack Graph', icon: NetworkIcon },
  { href: '/hosts',        label: 'Hosts',        icon: ServerIcon },
  { href: '/timeline',     label: 'Timeline',     icon: ClockIcon },
  { href: '/flows',        label: 'Flows',        icon: ListIcon },
  { href: '/admin',        label: 'Admin',        icon: SettingsIcon, minRole: 'admin' },
];

export function Sidebar() {
  const router = useRouter();
  const hasRole = useUserStore((state) => state.hasRole);

  return (
    <aside
      className="w-60 shrink-0 glass m-3 mr-0 p-4 flex flex-col gap-2"
      aria-label="Primary"
    >
      <div className="px-2 py-3 mb-3">
        <p className="text-xs uppercase tracking-[0.25em] text-muted">LateD</p>
        <p className="text-lg font-semibold text-cyan">SOC Command</p>
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
              'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
              active
                ? 'bg-cyan/10 text-cyan border border-cyan/50'
                : 'text-muted hover:text-ink hover:bg-elevated/60',
            )}
          >
            <Icon size={16} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </aside>
  );
}
