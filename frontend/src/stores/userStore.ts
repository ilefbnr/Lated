// =============================================================================
// stores/userStore.ts — current user identity
// =============================================================================
//
// Holds the result of GET /auth/me and the resolved bearer token. The token
// is also persisted in localStorage via apiClient.setAuthToken so a hard
// refresh keeps the analyst signed in.
// =============================================================================

import { create } from 'zustand';

import { authService, hasRole, type AuthUser, type Role } from '@/services/authService';
import { clearAuthToken, setAuthToken } from '@/services/apiClient';

interface UserState {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  hydrate: () => Promise<void>;
  login: (token: string) => Promise<AuthUser | null>;
  logout: () => void;
  hasRole: (minimum: Role) => boolean;
}

export const useUserStore = create<UserState>((set, get) => ({
  user: null,
  loading: false,
  error: null,

  hydrate: async () => {
    set({ loading: true, error: null });
    try {
      const user = await authService.me();
      set({ user, loading: false });
    } catch (err) {
      set({
        user: null,
        loading: false,
        error: err instanceof Error ? err.message : 'failed to load identity',
      });
    }
  },

  login: async (token: string) => {
    setAuthToken(token);
    set({ loading: true, error: null });
    try {
      const user = await authService.me();
      set({ user, loading: false });
      return user;
    } catch (err) {
      clearAuthToken();
      set({
        user: null,
        loading: false,
        error: err instanceof Error ? err.message : 'invalid token',
      });
      return null;
    }
  },

  logout: () => {
    clearAuthToken();
    set({ user: null, error: null });
  },

  hasRole: (minimum: Role) => hasRole(get().user?.role ?? null, minimum),
}));
