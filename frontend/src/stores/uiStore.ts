// =============================================================================
// stores/uiStore.ts — cross-cutting UI state
// =============================================================================

import { create } from 'zustand';

import type { FlowsFilters } from '@/services/flowsService';

export interface UIState {
  wsConnected: boolean;
  env: 'development' | 'staging' | 'production';
  theme: 'dark' | 'light';
  selectedHostId: string | null;
  selectedPathId: string | null;
  flowsFilters: FlowsFilters;
  sidebarCollapsed: boolean;
  setWsConnected: (connected: boolean) => void;
  setTheme: (theme: 'dark' | 'light') => void;
  toggleTheme: () => void;
  setSelectedHost: (hostId: string | null) => void;
  setSelectedPath: (pathId: string | null) => void;
  setFlowsFilters: (filters: FlowsFilters) => void;
  toggleSidebar: () => void;
}

const ENV = (process.env.NEXT_PUBLIC_ENV ?? 'development') as UIState['env'];
const DEFAULT_THEME: UIState['theme'] = 'dark';

export const useUIStore = create<UIState>((set, get) => ({
  wsConnected: false,
  env: ENV,
  theme: DEFAULT_THEME,
  selectedHostId: null,
  selectedPathId: null,
  flowsFilters: {},
  sidebarCollapsed: false,

  setWsConnected: (connected) => set({ wsConnected: connected }),
  setTheme: (theme) => set({ theme }),
  toggleTheme: () => set({ theme: get().theme === 'dark' ? 'light' : 'dark' }),
  setSelectedHost: (hostId) => set({ selectedHostId: hostId }),
  setSelectedPath: (pathId) => set({ selectedPathId: pathId }),
  setFlowsFilters: (filters) => set({ flowsFilters: filters }),
  toggleSidebar: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
}));
