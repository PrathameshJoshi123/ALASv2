"use client";

import { BarChart3, TrendingUp, ShieldAlert, FileText, CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function AnalyticsPage() {
  return (
    <div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
            <span>System</span> / <span>Analytics & Metrics</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Compliance & Operations Analytics
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Monitor contract turnaround velocity, Indian Contract Act compliance rates, and risk distribution.
          </p>
        </div>
      </div>

      {/* 2. Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Contracts Audited (30 Days)</CardDescription>
            <CardTitle className="text-2xl font-bold text-foreground">24</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-emerald-600 font-semibold flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>+18% compared to prior month</span>
            </p>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Average Portfolio Risk Score</CardDescription>
            <CardTitle className="text-2xl font-bold text-foreground">34%</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Low-to-moderate corporate risk exposure
            </p>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Statutory Flags Triggered</CardDescription>
            <CardTitle className="text-2xl font-bold text-red-600">7</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Primarily Section 27 (Post-term non-competes)
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 3. Statutory Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Indian Contract Act Audit Breakdown</CardTitle>
            <CardDescription className="text-xs">Distribution of detected statutory risks</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between text-xs p-2.5 rounded bg-muted/40">
              <span className="font-semibold text-foreground">Section 27 (Restraint of Trade)</span>
              <Badge variant="destructive">5 Flags</Badge>
            </div>
            <div className="flex items-center justify-between text-xs p-2.5 rounded bg-muted/40">
              <span className="font-semibold text-foreground">Section 74 (Penal Damages)</span>
              <Badge variant="warning">2 Flags</Badge>
            </div>
            <div className="flex items-center justify-between text-xs p-2.5 rounded bg-muted/40">
              <span className="font-semibold text-foreground">Section 28 (Arbitration & Seat)</span>
              <Badge variant="success">All Validated</Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Autonomous Drafting Throughput</CardTitle>
            <CardDescription className="text-xs">Synthesis pipeline metrics</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between text-xs p-2.5 rounded bg-muted/40">
              <span className="font-semibold text-foreground">Average Synthesis Duration</span>
              <span className="font-mono text-muted-foreground">18.4 seconds</span>
            </div>
            <div className="flex items-center justify-between text-xs p-2.5 rounded bg-muted/40">
              <span className="font-semibold text-foreground">Indian Kanoon Precedents Cited</span>
              <span className="font-mono text-muted-foreground">84 citations</span>
            </div>
            <div className="flex items-center justify-between text-xs p-2.5 rounded bg-muted/40">
              <span className="font-semibold text-foreground">Redline Acceptance Rate</span>
              <span className="font-mono text-emerald-600 font-bold">92%</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
