// =============================================================================
// hooks/useUser.ts — current user binding
// =============================================================================

import { useEffect } from 'react';

import type { AuthUser, Role } from '@/services/authService';
import { useUserStore } from '@/stores/userStore';

export interface UseUser {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  hasRole: (minimum: Role) => boolean;
  login: (token: string) => Promise<AuthUser | null>;
  logout: () => void;
}

export function useUser(autoHydrate = false): UseUser {
  const user = useUserStore((state) => state.user);
  const loading = useUserStore((state) => state.loading);
  const error = useUserStore((state) => state.error);
  const hasRole = useUserStore((state) => state.hasRole);
  const hydrate = useUserStore((state) => state.hydrate);
  const login = useUserStore((state) => state.login);
  const logout = useUserStore((state) => state.logout);

  useEffect(() => {
    if (!autoHydrate) return;
    if (user !== null || loading) return;
    void hydrate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoHydrate]);

  return { user, loading, error, hasRole, login, logout };
}
