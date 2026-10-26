"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Scale, Bell, Settings, Search, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

export default function Header() {
  const pathname = usePathname();

  const primaryTabs = [
    { name: "Overview", href: "/dashboard" },
    { name: "Contract Analysis", href: "/dashboard/analysis" },
    { name: "Contract Drafting", href: "/dashboard/drafting" },
    { name: "Case Files", href: "/dashboard/cases" },
  ];

  return (
    <header className="h-14 bg-card border-b border-border px-6 flex items-center justify-between shrink-0 select-none z-20 no-print">
      <div className="flex items-center gap-8 h-full">
        {/* Brand */}
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-primary text-white flex items-center justify-center font-extrabold text-xs shadow-sm">
            <Scale className="w-3.5 h-3.5" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="font-bold text-base tracking-tight text-foreground">
              ALAS
            </span>
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-widest hidden sm:inline">
              Legal OS
            </span>
          </div>
        </Link>

        {/* Top Workflow Switcher */}
        <nav className="hidden md:flex h-full items-end gap-6">
          {primaryTabs.map((tab) => {
            const isActive =
              tab.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(tab.href);

            return (
              <Link
                key={tab.name}
                href={tab.href}
                className={cn(
                  "text-xs font-semibold tracking-wide pb-3.5 border-b-2 transition-colors",
                  isActive
                    ? "text-primary border-primary font-bold"
                    : "text-muted-foreground border-transparent hover:text-foreground hover:border-slate-300",
                )}
              >
                {tab.name}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Global Utilities */}
      <div className="flex items-center gap-4">
        {/* Engine Status */}
        <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200/60 text-emerald-800 text-[11px] font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>Kanoon & ICA Engine Online</span>
        </div>

        {/* Action icons */}
        <div className="flex items-center gap-1">
          <Link
            href="/dashboard/settings"
            className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </header>
  );
}
