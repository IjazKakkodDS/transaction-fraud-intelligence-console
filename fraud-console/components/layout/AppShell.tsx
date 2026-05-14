"use client";

import { useState } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { Sidebar } from "@/components/layout/Sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="fraud-shell relative flex h-dvh flex-col overflow-hidden">
      {/* Static ambient depth layer — non-interactive, below all content */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="bg-orb bg-orb-1" />
        <div className="bg-orb bg-orb-2" />
        <div className="bg-grid" />
      </div>

      <TopBar onOpenDrawer={() => setDrawerOpen(true)} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar isDrawerOpen={drawerOpen} onCloseDrawer={() => setDrawerOpen(false)} />
        <main className="flex-1 overflow-y-auto px-4 pt-7 pb-8 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
