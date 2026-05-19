// =============================================================================
// layouts/SOCLayout.tsx — SOC command-center shell
// =============================================================================

import type { ReactNode } from 'react';

import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export interface SOCLayoutProps {
  children: ReactNode;
}

export function SOCLayout({ children }: SOCLayoutProps) {
  return (
    <div className="flex min-h-screen h-screen bg-canvas text-ink">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 overflow-y-auto relative">{children}</main>
      </div>
    </div>
  );
}
