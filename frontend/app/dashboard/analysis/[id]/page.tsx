"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AlertCircle,
  CheckCircle,
  Info,
  Loader2,
  ArrowLeft,
  FileText,
  RotateCw,
  MessageSquare,
  ShieldAlert,
  Scale,
  Edit3,
  ExternalLink,
  BookOpen,
  Filter,
  Search,
  CheckSquare,
  Square,
  Copy,
  PenTool,
} from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { JuristChatDrawer } from "@/components/dashboard/JuristChatDrawer";
import { ClauseRedlineModal } from "@/components/dashboard/ClauseRedlineModal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

interface Clause {
  id: string;
  clause_type: string;
  section_title: string;
  raw_text: string;
  severity: string;
  risk_description: string;
  legal_reasoning: string;
  confidence_score: number;
}

/**
 * Reconstructs fragmented OCR line breaks into smooth, professional legal paragraphs.
 */
function formatOcrDocumentText(raw: string): string {
  if (!raw) return "";
  const lines = raw.split("\n");
  const paragraphs: string[] = [];
  let buffer: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (!trimmed) {
      if (buffer.length > 0) {
        paragraphs.push(buffer.join(" "));
        buffer = [];
      }
    } else {
      const isHeader =
        /^(agreement|indenture|clause|section|schedule|article|\d+\.)/i.test(trimmed) &&
        trimmed.length < 80;

      if (isHeader && buffer.length > 0) {
        paragraphs.push(buffer.join(" "));
        buffer = [];
      }

      buffer.push(trimmed);

      if (isHeader) {
        paragraphs.push(buffer.join(" "));
        buffer = [];
      }
    }
  }

  if (buffer.length > 0) {
    paragraphs.push(buffer.join(" "));
  }

  return paragraphs.join("\n\n");
}

export default function AnalysisDetailPage() {
  const params = useParams();
  const router = useRouter();
  const contractId = params.id as string;

  const [contract, setContract] = useState<any>(null);
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("summary");
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [selectedClauseForEdit, setSelectedClauseForEdit] = useState<Clause | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  // Filters
  const [clauseSeverityFilter, setClauseSeverityFilter] = useState("ALL");
  const [clauseSearch, setClauseSearch] = useState("");
  const [obligationCategoryFilter, setObligationCategoryFilter] = useState("ALL");
  const [riskCategoryFilter, setRiskCategoryFilter] = useState("ALL");
  const [resolvedQuestions, setResolvedQuestions] = useState<Set<number>>(new Set());

  const fetchContractData = async () => {
    try {
      const [contractData, analysisData] = await Promise.allSettled([
        apiClient.getContractDetails(contractId),
        apiClient.getContractAnalysis(contractId),
      ]);

      if (contractData.status === "fulfilled") {
        setContract(contractData.value);
      }
      if (analysisData.status === "fulfilled") {
        setAnalysis(analysisData.value);
        if (analysisData.value?.clauses) {
          setClauses(analysisData.value.clauses);
        }
      }
    } catch (err) {
      console.error("Error fetching analysis details", err);
      toast.error("Failed to load contract details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (contractId) {
      fetchContractData();
    }
  }, [contractId]);

  const handleReanalyze = async () => {
    try {
      setIsAnalyzing(true);
      await apiClient.analyzeContract(contractId);
      toast.success("AI Legal Analysis initiated with Indian Kanoon research");
      fetchContractData();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to trigger analysis");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const toggleQuestionResolved = (idx: number) => {
    setResolvedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  const getRiskScoreColor = (score: number) => {
    if (score >= 70) return "text-red-700 bg-red-50 border-red-200";
    if (score >= 40) return "text-amber-700 bg-amber-50 border-amber-200";
    return "text-emerald-700 bg-emerald-50 border-emerald-200";
  };

  const getSeverityBadge = (sev: string) => {
    const s = sev?.toUpperCase();
    if (s === "CRITICAL" || s === "HIGH") return <Badge variant="destructive">{sev}</Badge>;
    if (s === "MEDIUM") return <Badge variant="warning">{sev}</Badge>;
    return <Badge variant="success">{sev || "INFO"}</Badge>;
  };

  // Filtered Clauses
  const filteredClauses = useMemo(() => {
    return clauses.filter((c) => {
      const matchSev =
        clauseSeverityFilter === "ALL" ||
        c.severity?.toUpperCase() === clauseSeverityFilter.toUpperCase();
      const matchQuery =
        !clauseSearch ||
        c.section_title?.toLowerCase().includes(clauseSearch.toLowerCase()) ||
        c.clause_type?.toLowerCase().includes(clauseSearch.toLowerCase()) ||
        c.raw_text?.toLowerCase().includes(clauseSearch.toLowerCase());
      return matchSev && matchQuery;
    });
  }, [clauses, clauseSeverityFilter, clauseSearch]);

  // Unique Obligation Categories
  const obligationsList = analysis?.obligations || [];
  const obligationCategories = useMemo(() => {
    const cats = new Set<string>();
    obligationsList.forEach((ob: any) => {
      const cat = ob.category || ob.details?.category || "General";
      if (cat) cats.add(cat);
    });
    return Array.from(cats);
  }, [obligationsList]);

  // Unique Risk Categories
  const risksList = analysis?.risks || [];
  const riskCategories = useMemo(() => {
    const cats = new Set<string>();
    risksList.forEach((r: any) => {
      const cat = r.category || r.details?.category || "General";
      if (cat) cats.add(cat);
    });
    return Array.from(cats);
  }, [risksList]);

  // Raw text formatted
  const rawText =
    contract?.extracted_text ||
    contract?.raw_text ||
    analysis?.analysis_markdown ||
    "";
  const formattedDocumentText = useMemo(() => formatOcrDocumentText(rawText), [rawText]);

  if (loading) {
    return (
      <div className="p-16 flex flex-col items-center justify-center text-xs text-muted-foreground gap-3 min-h-[50vh]">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
        <span>Loading institutional contract analysis suite...</span>
      </div>
    );
  }

  const riskScore = Number(analysis?.overall_risk_score || contract?.overall_risk_score || 0);
  const legalSources = analysis?.legal_sources || [];
  const unresolvedQuestions = analysis?.unresolved_questions || [];

  return (
    <div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8 pb-32">
      {/* 1. Page Header Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <button
            onClick={() => router.push("/dashboard/analysis")}
            className="inline-flex items-center text-xs font-semibold text-muted-foreground hover:text-foreground mb-2 gap-1 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Analysis Repository</span>
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-foreground truncate max-w-xl">
              {contract?.original_filename || contract?.markdown_file || "Contract Analysis"}
            </h1>
            <div className={`px-2.5 py-0.5 rounded-full border text-xs font-bold ${getRiskScoreColor(riskScore)}`}>
              Risk Score: {riskScore}/100
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Party: <span className="font-medium text-foreground">{contract?.counterparty_name || "Unspecified"}</span> • Type:{" "}
            <span className="font-medium text-foreground">{contract?.contract_type || "Commercial Agreement"}</span>
          </p>
        </div>

        {/* Global Page Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleReanalyze}
            disabled={isAnalyzing}
            className="text-xs"
          >
            {isAnalyzing ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <RotateCw className="w-3.5 h-3.5 mr-1.5" />
            )}
            Re-Audit
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsChatOpen(true)}
            className="text-xs"
          >
            <MessageSquare className="w-3.5 h-3.5 mr-1.5" />
            Ask AI Jurist
          </Button>

          <Button
            variant="default"
            size="sm"
            onClick={() => router.push(`/dashboard/drafting/editor/${contractId}`)}
            className="text-xs bg-slate-900 text-white hover:bg-slate-800"
          >
            <PenTool className="w-3.5 h-3.5 mr-1.5" />
            Open in Drafting Studio
          </Button>
        </div>
      </div>

      {/* 2. Key Metrics Strip */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <Card className="shadow-xs border-border">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Risk Score</p>
            <p className={`text-2xl font-bold mt-0.5 ${getRiskScoreColor(riskScore).split(" ")[0]}`}>
              {riskScore}%
            </p>
          </CardContent>
        </Card>

        <Card className="shadow-xs border-border">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Critical Issues</p>
            <p className="text-2xl font-bold text-red-600 mt-0.5">{analysis?.critical_issues || 0}</p>
          </CardContent>
        </Card>

        <Card className="shadow-xs border-border">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">High / Med Flags</p>
            <p className="text-2xl font-bold text-amber-600 mt-0.5">
              {(analysis?.high_issues || 0) + (analysis?.medium_issues || 0)}
            </p>
          </CardContent>
        </Card>

        <Card className="shadow-xs border-border">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Clauses Audited</p>
            <p className="text-2xl font-bold text-foreground mt-0.5">{clauses.length || 0}</p>
          </CardContent>
        </Card>

        <Card className="shadow-xs border-border">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Obligations</p>
            <p className="text-2xl font-bold text-indigo-600 mt-0.5">{obligationsList.length || 0}</p>
          </CardContent>
        </Card>

        <Card className="shadow-xs border-border">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Kanoon Precedents</p>
            <p className="text-2xl font-bold text-purple-600 mt-0.5">{legalSources.length || 0}</p>
          </CardContent>
        </Card>
      </div>

      {/* 3. Main Analysis Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-slate-100 p-1 rounded-lg border border-border">
          <TabsTrigger value="summary" className="text-xs font-medium">
            Executive Summary & Kanoon
          </TabsTrigger>
          <TabsTrigger value="clauses" className="text-xs font-medium">
            Clause Inspector & Redline ({clauses.length})
          </TabsTrigger>
          <TabsTrigger value="obligations" className="text-xs font-medium">
            Obligations ({obligationsList.length})
          </TabsTrigger>
          <TabsTrigger value="risks" className="text-xs font-medium">
            Categorized Risks ({risksList.length})
          </TabsTrigger>
          <TabsTrigger value="questions" className="text-xs font-medium">
            Due Diligence ({unresolvedQuestions.length})
          </TabsTrigger>
          <TabsTrigger value="text" className="text-xs font-medium">
            Document Text
          </TabsTrigger>
        </TabsList>

        {/* ========================================================================= */}
        {/* TAB 1: Executive Summary & Indian Kanoon Authorities */}
        {/* ========================================================================= */}
        <TabsContent value="summary" className="space-y-6 mt-4">
          <Card className="shadow-xs border-border">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <Scale className="w-4 h-4 text-blue-600" />
                    Legal Executive Summary
                  </CardTitle>
                  <CardDescription className="text-xs text-muted-foreground mt-0.5">
                    Grounded under the Indian Contract Act 1872 and commercial guidelines
                  </CardDescription>
                </div>
                <Badge variant="outline" className="text-[10px] uppercase font-mono">
                  Autonomous Legal Synthesis
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-foreground leading-relaxed whitespace-pre-wrap font-sans">
                {analysis?.analysis_summary || analysis?.summary || "Contract analysis completed."}
              </p>
            </CardContent>
          </Card>

          {/* Key Findings & Recommendations Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="shadow-xs border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <CheckCircle className="w-3.5 h-3.5 text-blue-600" />
                  Key Legal Findings
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {analysis?.key_findings && analysis.key_findings.length > 0 ? (
                  analysis.key_findings.map((item: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2.5 text-xs text-foreground">
                      <span className="text-blue-600 font-bold mt-0.5 shrink-0">•</span>
                      <span className="leading-relaxed">{item}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground italic">No specific legal findings recorded.</p>
                )}
              </CardContent>
            </Card>

            <Card className="shadow-xs border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <ShieldAlert className="w-3.5 h-3.5 text-emerald-600" />
                  Actionable Recommendations
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {analysis?.recommended_actions && analysis.recommended_actions.length > 0 ? (
                  analysis.recommended_actions.map((item: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2.5 text-xs text-foreground">
                      <span className="text-emerald-600 font-bold mt-0.5 shrink-0">✓</span>
                      <span className="leading-relaxed">{item}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground italic">No actionable recommendations recorded.</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Researched Indian Kanoon Precedents & Statutory Authorities */}
          <Card className="shadow-xs border-border">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm font-bold flex items-center gap-2 text-slate-900">
                  <BookOpen className="w-4 h-4 text-purple-600" />
                  Researched Indian Kanoon Precedents & Statutory Authorities
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-0.5">
                  Statutes and Supreme Court / High Court rulings verified for this agreement
                </CardDescription>
              </div>
              <Badge variant="outline" className="text-xs text-purple-700 bg-purple-50 border-purple-200">
                {legalSources.length} Authorities Verified
              </Badge>
            </CardHeader>
            <CardContent>
              {legalSources.length === 0 ? (
                <div className="p-8 text-center rounded-lg border border-dashed border-border bg-slate-50/50">
                  <BookOpen className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  <p className="text-xs text-slate-600 font-medium">
                    No external Indian Kanoon authorities recorded for this document yet.
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-1">
                    Click &quot;Re-Audit&quot; to trigger live scraping and judicial lookup on indiankanoon.org.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {legalSources.map((source: any, idx: number) => (
                    <div
                      key={source.doc_id || idx}
                      className="p-4 rounded-xl bg-slate-50/60 border border-border hover:border-purple-300 transition space-y-2.5"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 bg-purple-100 text-purple-800 text-[10px] font-bold rounded">
                              {source.statute_or_court || "Indian Authority"}
                            </span>
                            {source.doc_id && (
                              <span className="text-[10px] text-muted-foreground font-mono">
                                Doc ID: {source.doc_id}
                              </span>
                            )}
                          </div>
                          <h4 className="font-bold text-slate-900 text-xs leading-snug">
                            {source.title}
                          </h4>
                        </div>
                        {source.url && (
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-lg bg-white border border-border text-purple-600 hover:text-purple-800 hover:bg-purple-50 transition shrink-0"
                            title="View source on Indian Kanoon"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </div>

                      {source.relevance_summary && (
                        <p className="text-[11px] text-slate-700 leading-relaxed bg-white p-2.5 rounded-lg border border-border">
                          <strong className="font-semibold text-slate-800">Relevance:</strong>{" "}
                          {source.relevance_summary}
                        </p>
                      )}

                      {source.key_provision_or_ratio && (
                        <p className="text-[11px] text-purple-900 bg-purple-50 p-2 rounded border border-purple-200/80 font-mono line-clamp-3">
                          {source.key_provision_or_ratio}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ========================================================================= */}
        {/* TAB 2: Clause Inspector & Redline */}
        {/* ========================================================================= */}
        <TabsContent value="clauses" className="space-y-4 mt-4">
          {/* Controls Strip: Severity Filter & Search */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-50 p-3 rounded-lg border border-border">
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <span className="text-xs font-semibold text-slate-600 flex items-center gap-1">
                <Filter className="w-3.5 h-3.5" /> Filter:
              </span>
              <div className="flex flex-wrap gap-1">
                {["ALL", "CRITICAL", "HIGH", "MEDIUM", "INFO"].map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setClauseSeverityFilter(sev)}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                      clauseSeverityFilter === sev
                        ? "bg-slate-900 text-white shadow-xs"
                        : "bg-white border border-border text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    {sev}
                  </button>
                ))}
              </div>
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search clauses..."
                value={clauseSearch}
                onChange={(e) => setClauseSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-border rounded-md focus:outline-hidden focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          {filteredClauses.length === 0 ? (
            <Card className="shadow-xs p-8 text-center text-xs text-muted-foreground">
              No clauses matching the current filter.
            </Card>
          ) : (
            filteredClauses.map((clause, idx) => (
              <Card key={clause.id || idx} className="shadow-xs hover:border-slate-300 transition-colors">
                <CardHeader className="p-4 pb-2 flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-foreground">
                      {clause.section_title || `Clause ${idx + 1}`}
                    </span>
                    <Badge variant="outline" className="text-[10px] uppercase font-mono">
                      {clause.clause_type}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    {getSeverityBadge(clause.severity)}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedClauseForEdit(clause);
                        setIsEditModalOpen(true);
                      }}
                      className="text-xs h-7 px-2.5 text-blue-600 hover:text-blue-700 hover:bg-blue-50 border-blue-200"
                    >
                      <Edit3 className="w-3 h-3 mr-1" />
                      Redraft with Suggestions
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="p-4 pt-2 space-y-2.5">
                  <div className="p-3 bg-muted/40 rounded-md text-xs font-mono text-slate-800 leading-relaxed border border-border/60">
                    {clause.raw_text}
                  </div>
                  {clause.risk_description && (
                    <div className="text-xs text-red-700 bg-red-50/70 p-2.5 rounded border border-red-200/70 leading-relaxed">
                      <strong>Risk Identified:</strong> {clause.risk_description}
                    </div>
                  )}
                  {clause.legal_reasoning && (
                    <div className="text-xs text-slate-700 p-2.5 bg-slate-50 rounded border border-border leading-relaxed">
                      <strong>Legal Analysis:</strong> {clause.legal_reasoning}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        {/* ========================================================================= */}
        {/* TAB 3: Categorized Obligations */}
        {/* ========================================================================= */}
        <TabsContent value="obligations" className="space-y-4 mt-4">
          <div className="flex flex-wrap items-center gap-1.5 bg-slate-50 p-3 rounded-lg border border-border">
            <span className="text-xs font-semibold text-slate-600 mr-2 flex items-center gap-1">
              <Filter className="w-3.5 h-3.5" /> Category:
            </span>
            <button
              onClick={() => setObligationCategoryFilter("ALL")}
              className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                obligationCategoryFilter === "ALL"
                  ? "bg-indigo-600 text-white shadow-xs"
                  : "bg-white border border-border text-slate-600 hover:bg-slate-100"
              }`}
            >
              All ({obligationsList.length})
            </button>
            {obligationCategories.map((cat) => (
              <button
                key={cat}
                onClick={() => setObligationCategoryFilter(cat)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                  obligationCategoryFilter === cat
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "bg-white border border-border text-slate-600 hover:bg-slate-100"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {obligationsList.length === 0 ? (
            <Card className="shadow-xs p-8 text-center text-xs text-muted-foreground">
              No obligations extracted for this contract yet.
            </Card>
          ) : (
            <div className="space-y-3">
              {obligationsList
                .filter((ob: any) => {
                  if (obligationCategoryFilter === "ALL") return true;
                  const c = ob.category || ob.details?.category || "General";
                  return String(c).toLowerCase() === obligationCategoryFilter.toLowerCase();
                })
                .map((ob: any, idx: number) => {
                  const text =
                    typeof ob === "string"
                      ? ob
                      : ob.description || ob.details?.description || JSON.stringify(ob);
                  const category = ob.category || ob.details?.category || "General";
                  const actor = ob.actor || ob.details?.actor;
                  const deadline = ob.deadline || ob.details?.deadline;

                  return (
                    <Card key={ob.id || idx} className="shadow-xs border-border">
                      <CardContent className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
                        <div className="space-y-1.5 flex-1">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-[10px] bg-indigo-50 text-indigo-700 border-indigo-200">
                              {category}
                            </Badge>
                            {actor && (
                              <span className="text-[11px] font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                                Party: {actor}
                              </span>
                            )}
                            {deadline && (
                              <span className="text-[11px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                                Deadline: {deadline}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-800 leading-relaxed font-medium">
                            {text}
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
            </div>
          )}
        </TabsContent>

        {/* ========================================================================= */}
        {/* TAB 4: Categorized Risks & Mitigations */}
        {/* ========================================================================= */}
        <TabsContent value="risks" className="space-y-4 mt-4">
          <div className="flex flex-wrap items-center gap-1.5 bg-slate-50 p-3 rounded-lg border border-border">
            <span className="text-xs font-semibold text-slate-600 mr-2 flex items-center gap-1">
              <Filter className="w-3.5 h-3.5" /> Category:
            </span>
            <button
              onClick={() => setRiskCategoryFilter("ALL")}
              className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                riskCategoryFilter === "ALL"
                  ? "bg-amber-600 text-white shadow-xs"
                  : "bg-white border border-border text-slate-600 hover:bg-slate-100"
              }`}
            >
              All ({risksList.length})
            </button>
            {riskCategories.map((cat) => (
              <button
                key={cat}
                onClick={() => setRiskCategoryFilter(cat)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                  riskCategoryFilter === cat
                    ? "bg-amber-600 text-white shadow-xs"
                    : "bg-white border border-border text-slate-600 hover:bg-slate-100"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {risksList.length === 0 ? (
            <Card className="shadow-xs p-8 text-center text-xs text-muted-foreground">
              No categorized contract risks flagged.
            </Card>
          ) : (
            <div className="space-y-3">
              {risksList
                .filter((r: any) => {
                  if (riskCategoryFilter === "ALL") return true;
                  const c = r.category || r.details?.category || "General";
                  return String(c).toLowerCase() === riskCategoryFilter.toLowerCase();
                })
                .map((r: any, idx: number) => {
                  const text =
                    typeof r === "string"
                      ? r
                      : r.description || r.details?.description || JSON.stringify(r);
                  const category = r.category || r.details?.category || "General";
                  const severity = String(r.severity || r.details?.severity || "MEDIUM").toUpperCase();
                  const mitigation = r.mitigation || r.details?.mitigation;
                  const affectedParty = r.affected_party || r.details?.affected_party;

                  return (
                    <Card key={r.id || idx} className="shadow-xs border-border">
                      <CardContent className="p-4 space-y-2">
                        <div className="flex items-center gap-2">
                          {getSeverityBadge(severity)}
                          <span className="text-[11px] font-semibold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                            {category}
                          </span>
                          {affectedParty && (
                            <span className="text-[11px] text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                              Affected: {affectedParty}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-800 font-medium leading-relaxed">
                          {text}
                        </p>
                        {mitigation && (
                          <div className="text-xs text-emerald-800 bg-emerald-50/70 p-2.5 rounded border border-emerald-200/70 leading-relaxed">
                            <strong>Recommended Mitigation:</strong> {mitigation}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
            </div>
          )}
        </TabsContent>

        {/* ========================================================================= */}
        {/* TAB 5: Due Diligence Checklist (Unresolved Questions) */}
        {/* ========================================================================= */}
        <TabsContent value="questions" className="space-y-4 mt-4">
          <Card className="shadow-xs border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-bold flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-amber-600" />
                Pre-Execution Due Diligence Checklist
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground">
                Clarify these ambiguities with counterparty or internal counsel prior to execution
              </CardDescription>
            </CardHeader>
            <CardContent>
              {unresolvedQuestions.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No open due diligence questions recorded.</p>
              ) : (
                <div className="space-y-2.5">
                  {unresolvedQuestions.map((q: string, idx: number) => {
                    const isChecked = resolvedQuestions.has(idx);
                    return (
                      <div
                        key={idx}
                        onClick={() => toggleQuestionResolved(idx)}
                        className={`p-3.5 rounded-lg border transition cursor-pointer flex items-start gap-3 ${
                          isChecked
                            ? "bg-slate-50 border-slate-200 opacity-60 line-through"
                            : "bg-white border-amber-200/80 hover:border-amber-400 shadow-xs"
                        }`}
                      >
                        <button className="mt-0.5 text-slate-400 hover:text-amber-600 shrink-0">
                          {isChecked ? (
                            <CheckSquare className="w-4 h-4 text-emerald-600" />
                          ) : (
                            <Square className="w-4 h-4 text-amber-600" />
                          )}
                        </button>
                        <div className="flex-1 space-y-0.5">
                          <p className="text-xs font-medium text-slate-800 leading-relaxed">
                            {q}
                          </p>
                          <p className="text-[10px] text-amber-700">
                            {isChecked
                              ? "Marked as clarified/reviewed"
                              : "Action Item: Resolve during commercial negotiation"}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ========================================================================= */}
        {/* TAB 6: Formatted Document Text */}
        {/* ========================================================================= */}
        <TabsContent value="text" className="mt-4">
          <Card className="shadow-xs border-border">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm font-bold flex items-center gap-2">
                  <FileText className="w-4 h-4 text-slate-600" />
                  Contract Document Text
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  OCR-reconstructed verbatim contract indenture
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(formattedDocumentText);
                  toast.success("Document text copied to clipboard");
                }}
                className="text-xs h-7"
              >
                <Copy className="w-3 h-3 mr-1" />
                Copy Text
              </Button>
            </CardHeader>
            <CardContent className="p-6">
              <div className="p-6 bg-slate-50/70 border border-border rounded-xl max-h-[70vh] overflow-y-auto">
                <div className="text-xs text-slate-800 font-sans leading-relaxed whitespace-pre-wrap selection:bg-blue-100 selection:text-blue-900">
                  {formattedDocumentText || "Document text preview is not available."}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Slide-out AI Jurist Drawer */}
      <JuristChatDrawer
        contractId={contractId}
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
      />

      {/* Clause Redline Modal */}
      {selectedClauseForEdit && (
        <ClauseRedlineModal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          contractId={contractId}
          clause={selectedClauseForEdit}
          onRevisionApplied={() => fetchContractData()}
        />
      )}
    </div>
  );
}
