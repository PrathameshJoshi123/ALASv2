"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  Search,
  Filter,
  Plus,
  ShieldAlert,
  Loader2,
  Trash2,
  ExternalLink,
  AlertTriangle,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface Contract {
  id: string;
  original_filename: string;
  markdown_file: string;
  counterparty_name: string;
  company_name: string;
  contract_type: string;
  status: string;
  created_at: string;
  overall_risk_score?: number;
}

export default function AnalysisRepositoryPage() {
  const router = useRouter();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [page, setPage] = useState(1);

  const fetchContracts = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getContracts(page, 20);
      const items = Array.isArray(data) ? data : data?.items || [];
      setContracts(items);
    } catch (error) {
      console.error("Failed to fetch contracts:", error);
      toast.error("Failed to load contracts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContracts();
  }, [page]);

  const handleDelete = async (e: React.MouseEvent, contractId: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to remove this contract from the analysis repository?")) return;
    try {
      await apiClient.deleteContract(contractId);
      toast.success("Contract removed");
      fetchContracts();
    } catch (err) {
      toast.error("Failed to delete contract");
    }
  };

  const filteredContracts = contracts.filter((contract) => {
    const matchesSearch =
      (contract.original_filename || contract.markdown_file || "")
        .toLowerCase()
        .includes(searchTerm.toLowerCase()) ||
      (contract.counterparty_name || contract.company_name || "")
        .toLowerCase()
        .includes(searchTerm.toLowerCase());
    const matchesStatus =
      statusFilter === "ALL" || contract.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: string) => {
    switch (status?.toUpperCase()) {
      case "COMPLETED":
        return <Badge variant="success">Audited</Badge>;
      case "PROCESSING":
      case "ANALYZING":
        return <Badge variant="info">In Review</Badge>;
      case "FAILED":
        return <Badge variant="destructive">Failed</Badge>;
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
            <span>Contract Analysis</span> / <span>Repository</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Contract Analysis Repository
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Review AI statutory risk assessments, Section 27/74 ICA audit findings, and clause redlines.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="default"
            onClick={() => router.push("/dashboard/analysis/upload")}
            className="text-xs"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Upload Contract
          </Button>
        </div>
      </div>

      {/* 2. Search & Filter Bar */}
      <Card className="shadow-sm">
        <CardContent className="p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search contracts by title, party, or filename..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 h-9 text-xs"
            />
          </div>
          <div className="flex items-center gap-2 w-full md:w-auto">
            <Filter className="w-3.5 h-3.5 text-muted-foreground" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 px-3 rounded-md border border-input bg-background text-xs font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="ALL">All Statuses</option>
              <option value="COMPLETED">Audited / Completed</option>
              <option value="PROCESSING">In Review</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* 3. Contracts Data Table */}
      <Card className="shadow-sm overflow-hidden">
        <CardContent className="p-0">
          {loading ? (
            <div className="p-12 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Loading contract analysis records...</span>
            </div>
          ) : filteredContracts.length === 0 ? (
            <div className="p-12 text-center text-xs text-muted-foreground space-y-3">
              <p>No contracts found matching your filters.</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push("/dashboard/analysis/upload")}
                className="text-xs"
              >
                Upload First Contract
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Document Name</TableHead>
                  <TableHead className="text-xs">Counterparty</TableHead>
                  <TableHead className="text-xs">Type</TableHead>
                  <TableHead className="text-xs">Status</TableHead>
                  <TableHead className="text-xs">Created At</TableHead>
                  <TableHead className="text-xs text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredContracts.map((c) => (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer hover:bg-muted/40 transition-colors"
                    onClick={() => router.push(`/dashboard/analysis/${c.id}`)}
                  >
                    <TableCell className="font-semibold text-xs text-foreground py-3.5">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                        <span className="truncate max-w-[240px]">
                          {c.original_filename || c.markdown_file || "Untitled Contract"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground py-3.5">
                      {c.counterparty_name || "Unspecified"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground py-3.5">
                      {c.contract_type || "NDA"}
                    </TableCell>
                    <TableCell className="py-3.5">
                      {getStatusBadge(c.status)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground py-3.5">
                      {c.created_at ? new Date(c.created_at).toLocaleDateString() : "Recent"}
                    </TableCell>
                    <TableCell className="text-xs text-right py-3.5">
                      <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => router.push(`/dashboard/analysis/${c.id}`)}
                          className="text-xs h-7 px-2 font-semibold text-accent hover:underline"
                        >
                          View Analysis
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => handleDelete(e, c.id)}
                          className="h-7 w-7 text-muted-foreground hover:text-destructive"
                          title="Delete contract"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
