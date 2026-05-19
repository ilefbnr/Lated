// =============================================================================
// services/authService.ts — identity surface
// =============================================================================

import { apiClient } from './apiClient';

export type Role = 'analyst' | 'supervisor' | 'admin';

export interface AuthUser {
  username: string;
  role: Role;
}

export const authService = {
  async me(): Promise<AuthUser> {
    return apiClient.get<AuthUser>('/auth/me');
  },
};

const ORDER: Record<Role, number> = { analyst: 1, supervisor: 2, admin: 3 };

export function hasRole(current: Role | null | undefined, minimum: Role): boolean {
  if (!current) return false;
  return ORDER[current] >= ORDER[minimum];
}
