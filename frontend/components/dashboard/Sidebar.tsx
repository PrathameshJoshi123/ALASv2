"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  ShieldAlert,
  PenTool,
  FolderKanban,
  BarChart3,
  Settings,
  Scale,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

const mainWorkflows: NavItem[] = [
  { href: "/dashboard/analysis", label: "Contract Analysis", icon: ShieldAlert },
  { href: "/dashboard/drafting", label: "Contract Drafting", icon: PenTool },
  { href: "/dashboard/cases", label: "Case Files", icon: FolderKanban },
];

const generalItems: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
];

const systemItems: NavItem[] = [
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();

  const isItemActive = (href: string) => {
    if (href === "/dashboard") {
      return pathname === "/dashboard";
    }
    return pathname.startsWith(href);
  };

  return (
    <aside className="w-64 bg-card border-r border-border flex flex-col shrink-0 h-full select-none no-print">
      {/* Firm & Department Info */}
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-md bg-primary text-primary-foreground flex items-center justify-center shrink-0 font-bold text-sm tracking-tight shadow-sm">
            <Scale className="w-4 h-4 text-white" />
          </div>
          <div className="overflow-hidden">
            <h3 className="font-semibold text-sm text-foreground truncate">
              Lexington & Co
            </h3>
            <p className="text-xs text-muted-foreground truncate">
              Indian Law & Corporate
            </p>
          </div>
        </div>

        {/* Quick Launch Button */}
        <div className="mt-4">
          <Link
            href="/dashboard/analysis/upload"
            className="flex items-center justify-center gap-2 w-full py-2 px-3 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-all shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Intake Document</span>
          </Link>
        </div>
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-6 overflow-y-auto">
        {/* Core Overview */}
        <div>
          <div className="px-3 mb-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
            Platform
          </div>
          <div className="space-y-1">
            {generalItems.map((item) => {
              const Icon = item.icon;
              const active = isItemActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors",
                    active
                      ? "bg-slate-100 text-foreground font-semibold border border-border"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/60",
                  )}
                >
                  <Icon className={cn("w-4 h-4", active ? "text-primary" : "text-muted-foreground")} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>

        {/* Legal Workflows */}
        <div>
          <div className="px-3 mb-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
            Legal Workflows
          </div>
          <div className="space-y-1">
            {mainWorkflows.map((item) => {
              const Icon = item.icon;
              const active = isItemActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-colors",
                    active
                      ? "bg-slate-100 text-foreground font-semibold border border-border"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/60",
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={cn("w-4 h-4", active ? "text-primary" : "text-muted-foreground")} />
                    <span>{item.label}</span>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>

        {/* System & Analytics */}
        <div>
          <div className="px-3 mb-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
            System
          </div>
          <div className="space-y-1">
            {systemItems.map((item) => {
              const Icon = item.icon;
              const active = isItemActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors",
                    active
                      ? "bg-slate-100 text-foreground font-semibold border border-border"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/60",
                  )}
                >
                  <Icon className={cn("w-4 h-4", active ? "text-primary" : "text-muted-foreground")} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Footer / User Profile */}
      <div className="p-3 border-t border-border bg-muted/30">
        <div className="flex items-center justify-between px-2 py-1.5">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full bg-slate-200 border border-border flex items-center justify-center font-bold text-xs text-slate-700">
              SA
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-semibold text-foreground truncate">
                Senior Associate
              </p>
              <p className="text-[10px] text-muted-foreground truncate">
                ICA & Arbitration Desk
              </p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
