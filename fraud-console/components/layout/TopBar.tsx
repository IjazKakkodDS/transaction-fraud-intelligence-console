"use client";

import { Menu } from "lucide-react";

interface TopBarProps {
  onOpenDrawer: () => void;
}

export function TopBar({ onOpenDrawer }: TopBarProps) {
  return (
    <header
      className="flex h-12 shrink-0 items-center px-4 sm:px-5"
      style={{
        background: "rgba(4,8,17,0.92)",
        borderBottom: "1px solid rgba(255,255,255,0.07)",
        backdropFilter: "blur(20px) saturate(160%)",
        WebkitBackdropFilter: "blur(20px) saturate(160%)",
      }}
    >
      {/* Hamburger — mobile only */}
      <button
        type="button"
        aria-label="Open navigation"
        onClick={onOpenDrawer}
        className="mr-3 flex h-8 w-8 shrink-0 items-center justify-center rounded-md lg:hidden"
        style={{
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.08)",
          color: "#8B949E",
        }}
      >
        <Menu className="h-3.5 w-3.5" />
      </button>

      {/* Brand */}
      <div className="flex min-w-0 flex-1 items-center">
        <span
          className="font-mono font-bold tracking-tight"
          style={{ color: "#F0F6FC", fontSize: "14px", letterSpacing: "-0.01em" }}
        >
          <span className="hidden sm:inline">Fraud Intelligence Console</span>
          <span className="sm:hidden">Fraud Console</span>
        </span>
        <span
          className="ml-3 hidden text-[11px] font-medium sm:inline"
          style={{ color: "#374151" }}
        >
          /
        </span>
        <span
          className="ml-3 hidden font-mono text-[11px] sm:inline"
          style={{ color: "#4B5563" }}
        >
          v1.0
        </span>
      </div>

      {/* Status chips */}
      <div className="flex shrink-0 items-center gap-2">
        <div
          className="hidden items-center gap-1.5 rounded-full px-2.5 py-1 sm:flex"
          style={{
            background: "rgba(16,185,129,0.07)",
            border: "1px solid rgba(16,185,129,0.18)",
          }}
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: "#10B981" }}
          />
          <span className="text-[11px] font-semibold" style={{ color: "#10B981" }}>
            Live System
          </span>
        </div>
        <div
          className="flex items-center gap-1.5 rounded-full px-2.5 py-1"
          style={{
            background: "rgba(16,185,129,0.07)",
            border: "1px solid rgba(16,185,129,0.18)",
          }}
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: "#10B981" }}
          />
          <span className="text-[11px] font-semibold" style={{ color: "#10B981" }}>
            <span className="hidden sm:inline">API Connected</span>
            <span className="sm:hidden">Live</span>
          </span>
        </div>
      </div>
    </header>
  );
}
