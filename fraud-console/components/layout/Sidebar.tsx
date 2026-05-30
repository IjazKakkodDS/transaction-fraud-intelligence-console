"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  X,
  LayoutDashboard,
  Gauge,
  ClipboardList,
  FileSearch,
  Activity,
  BarChart2,
  Send,
} from "lucide-react";

const navGroups = [
  {
    label: "OPERATIONS",
    items: [
      { label: "Overview",        href: "/",          icon: LayoutDashboard },
      { label: "Risk Command",    href: "/dashboard", icon: Gauge           },
      { label: "Review Queue",    href: "/queue",     icon: ClipboardList   },
      { label: "Transaction Intake", href: "/intake", icon: Send            },
      { label: "Risk Scan",       href: "/risk-scan", icon: FileSearch      },
    ],
  },
  {
    label: "WORKFLOW",
    items: [
      { label: "Workflow Events",      href: "/workflow/events",  icon: Activity  },
      { label: "Reliability Metrics",  href: "/workflow/metrics", icon: BarChart2 },
    ],
  },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <div className="space-y-5">
      {navGroups.map((group) => (
        <div key={group.label}>
          <p
            className="mb-2 px-4 text-[12px] font-bold uppercase tracking-[0.12em]"
            style={{ color: "#6B7280" }}
          >
            {group.label}
          </p>
          <ul className="flex flex-col gap-0.5 px-2">
            {group.items.map(({ label, href, icon: Icon }) => {
              const active =
                href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onNavigate}
                    className="flex items-center gap-2.5 rounded-md text-[13px] font-medium transition-colors"
                    style={
                      active
                        ? {
                            background: "rgba(34,211,238,0.10)",
                            color: "#22D3EE",
                            borderLeft: "2px solid #22D3EE",
                            paddingLeft: "10px",
                            paddingRight: "12px",
                            paddingTop: "9px",
                            paddingBottom: "9px",
                          }
                        : {
                            color: "#8B949E",
                            paddingLeft: "12px",
                            paddingRight: "12px",
                            paddingTop: "9px",
                            paddingBottom: "9px",
                          }
                    }
                    onMouseEnter={(e) => {
                      if (!active) {
                        (e.currentTarget as HTMLAnchorElement).style.background =
                          "rgba(255,255,255,0.04)";
                        (e.currentTarget as HTMLAnchorElement).style.color = "#C9D1D9";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!active) {
                        (e.currentTarget as HTMLAnchorElement).style.background =
                          "transparent";
                        (e.currentTarget as HTMLAnchorElement).style.color = "#8B949E";
                      }
                    }}
                  >
                    <Icon
                      className="h-4 w-4 shrink-0"
                      style={{ color: active ? "#22D3EE" : "#4B5563" }}
                    />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

interface SidebarProps {
  isDrawerOpen: boolean;
  onCloseDrawer: () => void;
}

export function Sidebar({ isDrawerOpen, onCloseDrawer }: SidebarProps) {
  useEffect(() => {
    if (!isDrawerOpen) {
      document.body.style.overflow = "";
      return;
    }
    document.body.style.overflow = "hidden";

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseDrawer();
    };
    window.addEventListener("keydown", handleEscape);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleEscape);
    };
  }, [isDrawerOpen, onCloseDrawer]);

  return (
    <>
      {/* Mobile backdrop */}
      {isDrawerOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={onCloseDrawer}
          className="fixed inset-0 z-40 lg:hidden"
          style={{
            background: "rgba(0,0,0,0.72)",
            backdropFilter: "blur(4px)",
          }}
        />
      )}

      {/* Mobile drawer — covers full viewport including TopBar area */}
      <aside
        className="fixed left-0 top-0 z-50 flex h-dvh flex-col lg:hidden"
        style={{
          width: "280px",
          background: "linear-gradient(160deg, #111827 0%, #0A0E17 100%)",
          borderRight: "1px solid rgba(255,255,255,0.09)",
          boxShadow: "4px 0 24px rgba(0,0,0,0.60)",
          transform: isDrawerOpen ? "translateX(0)" : "translateX(-100%)",
          transition: "transform 300ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        {/* Drawer header — mirrors TopBar height */}
        <div
          className="flex h-16 shrink-0 items-center justify-between px-5"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
        >
          <span
            className="font-mono text-[14px] font-bold tracking-tight"
            style={{ color: "#F0F6FC", letterSpacing: "-0.01em" }}
          >
            Fraud Console
          </span>
          <button
            type="button"
            aria-label="Close navigation"
            onClick={onCloseDrawer}
            className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors"
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.09)",
              color: "#8B949E",
            }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Nav */}
        <div className="flex-1 overflow-y-auto py-5">
          <NavItems onNavigate={onCloseDrawer} />
        </div>

        {/* Drawer footer */}
        <div
          className="shrink-0 px-5 py-4"
          style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
        >
          <p className="text-[12px]" style={{ color: "#4B5563" }}>
            System status:{" "}
            <span style={{ color: "#10B981" }}>Operational</span>
          </p>
          <p className="mt-1 text-[12px]" style={{ color: "#4B5563" }}>
            Fraud Intelligence Console
          </p>
        </div>
      </aside>

      {/* Desktop sidebar — static */}
      <nav
        className="hidden w-[210px] shrink-0 flex-col lg:flex"
        style={{
          background: "rgba(4,8,17,0.75)",
          backdropFilter: "blur(20px) saturate(160%)",
          WebkitBackdropFilter: "blur(20px) saturate(160%)",
          borderRight: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        {/* Desktop wordmark */}
        <div
          className="flex h-12 shrink-0 items-center px-5"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
        >
          <span
            className="font-mono text-[13px] font-bold tracking-tight"
            style={{ color: "#C9D1D9", letterSpacing: "-0.01em" }}
          >
            FraudIntel
          </span>
        </div>
        <div className="flex-1 overflow-y-auto py-5">
          <NavItems />
        </div>
      </nav>
    </>
  );
}
