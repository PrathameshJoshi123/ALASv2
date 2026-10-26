"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ShieldAlert,
  PenTool,
  FolderKanban,
  ArrowRight,
  Plus,
  FileText,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  TrendingUp,
  FileCheck,
} from "lucide-react";
import { apiClient } from "@/services/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function ExecutiveDashboard() {
  const router = useRouter();
  const [contracts, setContracts] = useState<any[]>([]);
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboardData() {
      try {
        setLoading(true);
        const [contractsRes, casesRes] = await Promise.allSettled([
          apiClient.getContracts(1, 5),
          apiClient.getCases(),
        ]);

        if (contractsRes.status === "fulfilled") {
          const items = Array.isArray(contractsRes.value)
            ? contractsRes.value
            : contractsRes.value?.items || [];
          setContracts(items.slice(0, 5));
        }

        if (casesRes.status === "fulfilled") {
          const caseItems = Array.isArray(casesRes.value) ? casesRes.value : [];
          setCases(caseItems.slice(0, 5));
        }
      } catch (err) {
        console.error("Error loading dashboard data", err);
      } finally {
        setLoading(false);
      }
    }

    loadDashboardData();
  }, []);

  const getStatusBadge = (status: string) => {
    switch (status?.toUpperCase()) {
      case "COMPLETED":
      case "ANALYZED":
        return <Badge variant="success">Completed</Badge>;
      case "PROCESSING":
      case "ANALYZING":
        return <Badge variant="info">In Review</Badge>;
      case "FAILED":
        return <Badge variant="destructive">Action Required</Badge>;
      default:
        return <Badge variant="outline">{status || "Pending"}</Badge>;
    }
  };

  return (
    <div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
            <span>Executive Command Center</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Legal Operations Overview
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Unified workspace for contract analysis, autonomous drafting, and multi-document litigation files.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => router.push("/dashboard/analysis/upload")}
            className="text-xs"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Upload Contract
          </Button>
          <Button
            variant="default"
            onClick={() => router.push("/dashboard/drafting")}
            className="text-xs"
          >
            <PenTool className="w-3.5 h-3.5 mr-1.5" />
            Draft New Agreement
          </Button>
        </div>
      </div>

      {/* 2. Core Legal Workflow Launchpads */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Pillar 1: Contract Analysis */}
        <Card className="hover:border-slate-400/80 transition-all shadow-sm flex flex-col justify-between">
          <CardHeader>
            <div className="w-10 h-10 rounded-md bg-blue-50 border border-blue-200/60 text-blue-700 flex items-center justify-center mb-2">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <CardTitle className="text-base">Contract Analysis</CardTitle>
            <CardDescription className="text-xs">
              Upload agreements to extract liabilities, classify clauses, and detect Section 27/74 ICA violations via Indian Kanoon research.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <Link
              href="/dashboard/analysis"
              className="inline-flex items-center text-xs font-semibold text-accent hover:underline gap-1"
            >
              <span>Explore Analysis Repository</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </CardContent>
        </Card>

        {/* Pillar 2: Contract Drafting */}
        <Card className="hover:border-slate-400/80 transition-all shadow-sm flex flex-col justify-between">
          <CardHeader>
            <div className="w-10 h-10 rounded-md bg-emerald-50 border border-emerald-200/60 text-emerald-700 flex items-center justify-center mb-2">
              <PenTool className="w-5 h-5" />
            </div>
            <CardTitle className="text-base">Contract Drafting</CardTitle>
            <CardDescription className="text-xs">
              Generate balanced or firm-favorable agreements using a 6-stage autonomous drafting engine and live redline studio.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <Link
              href="/dashboard/drafting"
              className="inline-flex items-center text-xs font-semibold text-accent hover:underline gap-1"
            >
              <span>Launch Drafting Studio</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </CardContent>
        </Card>

        {/* Pillar 3: Case Files */}
        <Card className="hover:border-slate-400/80 transition-all shadow-sm flex flex-col justify-between">
          <CardHeader>
            <div className="w-10 h-10 rounded-md bg-purple-50 border border-purple-200/60 text-purple-700 flex items-center justify-center mb-2">
              <FolderKanban className="w-5 h-5" />
            </div>
            <CardTitle className="text-base">Case Files (Litigation)</CardTitle>
            <CardDescription className="text-xs">
              Cross-examine multi-document case files, extract chronological event timelines, and interrogate exhibits with AI Jurist.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <Link
              href="/dashboard/cases"
              className="inline-flex items-center text-xs font-semibold text-accent hover:underline gap-1"
            >
              <span>Manage Litigation Files</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* 3. Operational Overview & Recent Documents */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Analyzed Contracts */}
        <Card className="lg:col-span-2 shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-sm font-semibold">
                Recent Contract Analyses
              </CardTitle>
              <CardDescription className="text-xs">
                Audited documents and risk status
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push("/dashboard/analysis")}
              className="text-xs"
            >
              View all
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading analysis repository...</span>
              </div>
            ) : contracts.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground">
                No contracts analyzed yet. Click "Upload Contract" to begin.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Document Name</TableHead>
                    <TableHead className="text-xs">Type</TableHead>
                    <TableHead className="text-xs">Counterparty</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-xs text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {contracts.map((c) => (
                    <TableRow
                      key={c.id}
                      className="cursor-pointer hover:bg-muted/40"
                      onClick={() => router.push(`/dashboard/analysis/${c.id}`)}
                    >
                      <TableCell className="font-medium text-xs text-foreground py-3">
                        <div className="flex items-center gap-2">
                          <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                          <span className="truncate max-w-[180px]">
                            {c.original_filename || c.markdown_file || "Untitled"}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground py-3">
                        {c.contract_type || "Commercial"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground py-3">
                        {c.counterparty_name || "N/A"}
                      </TableCell>
                      <TableCell className="py-3">
                        {getStatusBadge(c.status)}
                      </TableCell>
                      <TableCell className="text-xs text-right py-3">
                        <span className="text-accent hover:underline font-semibold">
                          Inspect
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Active Litigation Cases */}
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-sm font-semibold">
                Active Case Files
              </CardTitle>
              <CardDescription className="text-xs">
                Litigation matters & timelines
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push("/dashboard/cases")}
              className="text-xs"
            >
              View all
            </Button>
          </CardHeader>
          <CardContent className="space-y-3 pt-0">
            {loading ? (
              <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading cases...</span>
              </div>
            ) : cases.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground">
                No active case files. Create a case to index multiple exhibits.
              </div>
            ) : (
              cases.map((cs) => (
                <div
                  key={cs.id}
                  onClick={() => router.push(`/dashboard/cases/${cs.id}/results`)}
                  className="p-3 rounded-md border border-border hover:bg-muted/40 cursor-pointer transition-colors"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-xs text-foreground truncate max-w-[180px]">
                      {cs.title}
                    </span>
                    <Badge variant="outline" className="text-[10px]">
                      {cs.documents_count || cs.documents?.length || 0} Docs
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground line-clamp-1">
                    {cs.description || "Litigation matter under review."}
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
