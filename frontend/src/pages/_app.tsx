// =============================================================================
// pages/_app.tsx — Next.js custom App
// =============================================================================

import { useEffect } from 'react';
import { useRouter } from 'next/router';
import type { AppProps } from 'next/app';
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';

import '@/styles/globals.css';

// Register layout extension once at app boot, before any canvas mounts.
if (typeof window !== 'undefined') {
  // cytoscape.use is idempotent across HMR reloads in dev.
  try { cytoscape.use(fcose); } catch { /* already registered */ }
}

import { SOCLayout } from '@/layouts/SOCLayout';
import { useBootstrapWebSocket } from '@/hooks/useWebSocket';
import { useUserStore } from '@/stores/userStore';

const PUBLIC_ROUTES = new Set(['/login']);

export default function LateDApp({ Component, pageProps, router }: AppProps) {
  return (
    <AppShell pathname={router.pathname}>
      <Component {...pageProps} />
    </AppShell>
  );
}

interface AppShellProps {
  pathname: string;
  children: React.ReactNode;
}

function AppShell({ pathname, children }: AppShellProps) {
  const router = useRouter();
  const user = useUserStore((state) => state.user);
  const loading = useUserStore((state) => state.loading);
  const hydrate = useUserStore((state) => state.hydrate);

  // Resolve current identity on first mount.
  useEffect(() => {
    if (user !== null) return;
    void hydrate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Guard non-public routes — redirect to /login when no user.
  useEffect(() => {
    if (PUBLIC_ROUTES.has(pathname)) return;
    if (loading) return;
    if (user === null) {
      void router.replace('/login');
    }
  }, [pathname, user, loading, router]);

  if (PUBLIC_ROUTES.has(pathname)) {
    return <>{children}</>;
  }

  return (
    <AuthenticatedShell user={user} loading={loading}>
      {children}
    </AuthenticatedShell>
  );
}

interface AuthenticatedShellProps {
  user: ReturnType<typeof useUserStore.getState>['user'];
  loading: boolean;
  children: React.ReactNode;
}

function AuthenticatedShell({ user, loading, children }: AuthenticatedShellProps) {
  useBootstrapWebSocket();

  if (user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-canvas text-muted text-sm">
        {loading ? 'authenticating…' : 'redirecting…'}
      </div>
    );
  }

  return <SOCLayout>{children}</SOCLayout>;
}
