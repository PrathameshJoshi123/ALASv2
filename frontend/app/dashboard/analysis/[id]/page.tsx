"use client";

import { useEffect, useState } from "react";
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
      toast.success("AI Analysis initiated with Indian Kanoon research");
      fetchContractData();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to trigger analysis");
    } finally {
      setIsAnalyzing(false);
    }
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

  if (loading) {
    return (
      <div className="p-16 flex flex-col items-center justify-center text-xs text-muted-foreground gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
        <span>Loading contract analysis suite...</span>
      </div>
    );
  }

  const riskScore = Number(analysis?.overall_risk_score || contract?.overall_risk_score || 0);

  return (
    <div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8">
      {/* 1. Header Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <button
            onClick={() => router.push("/dashboard/analysis")}
            className="inline-flex items-center text-xs font-semibold text-muted-foreground hover:text-foreground mb-2 gap-1"
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
            Party: {contract?.counterparty_name || "Unspecified"} • Type: {contract?.contract_type || "Commercial Agreement"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleReanalyze}
            loading={isAnalyzing}
            className="text-xs"
          >
            <RotateCw className="w-3.5 h-3.5 mr-1.5" />
            Re-Audit
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={() => setIsChatOpen(true)}
            className="text-xs"
          >
            <MessageSquare className="w-3.5 h-3.5 mr-1.5" />
            Ask AI Jurist
          </Button>
        </div>
      </div>

      {/* 2. Key Metrics Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="shadow-sm">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground font-medium">Risk Score</p>
            <p className="text-2xl font-bold text-foreground mt-1">{riskScore}%</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground font-medium">Critical Issues</p>
            <p className="text-2xl font-bold text-red-600 mt-1">{analysis?.critical_issues || 0}</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground font-medium">High / Medium Flags</p>
            <p className="text-2xl font-bold text-amber-600 mt-1">
              {(analysis?.high_issues || 0) + (analysis?.medium_issues || 0)}
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground font-medium">Extracted Clauses</p>
            <p className="text-2xl font-bold text-foreground mt-1">{clauses.length || 0}</p>
          </CardContent>
        </Card>
      </div>

      {/* 3. Main Analysis Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="summary">Executive Summary & Findings</TabsTrigger>
          <TabsTrigger value="clauses">Clause Inspector & Redline ({clauses.length})</TabsTrigger>
          <TabsTrigger value="text">Document Text</TabsTrigger>
        </TabsList>

        {/* Tab 1: Executive Summary */}
        <TabsContent value="summary" className="space-y-6">
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="text-sm font-semibold">Legal Executive Summary</CardTitle>
              <CardDescription className="text-xs">
                AI synthesis under Indian Contract Act 1872 and commercial guidelines
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                {analysis?.analysis_summary || "Contract analysis processing or summary not available."}
              </p>
            </CardContent>
          </Card>

          {/* Key Findings & Recommendations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="shadow-sm">
              <CardHeader>
                <CardTitle className="text-sm font-semibold">Key Legal Findings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {analysis?.key_findings && analysis.key_findings.length > 0 ? (
                  analysis.key_findings.map((item: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2 text-xs text-foreground">
                      <span className="text-accent font-bold mt-0.5">•</span>
                      <span>{item}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground">No specific findings flagged.</p>
                )}
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader>
                <CardTitle className="text-sm font-semibold">Actionable Recommendations</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {analysis?.recommended_actions && analysis.recommended_actions.length > 0 ? (
                  analysis.recommended_actions.map((item: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2 text-xs text-foreground">
                      <span className="text-emerald-600 font-bold mt-0.5">✓</span>
                      <span>{item}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground">No explicit actions recommended.</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Tab 2: Clause Inspector */}
        <TabsContent value="clauses" className="space-y-4">
          {clauses.length === 0 ? (
            <Card className="shadow-sm p-8 text-center text-xs text-muted-foreground">
              No clauses extracted for this document yet. Click "Re-Audit" to extract clauses.
            </Card>
          ) : (
            clauses.map((clause, idx) => (
              <Card key={clause.id || idx} className="shadow-sm hover:border-slate-300 transition-colors">
                <CardHeader className="p-4 pb-2 flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-foreground">
                      {clause.section_title || `Clause ${idx + 1}`}
                    </span>
                    <Badge variant="outline" className="text-[10px] uppercase">
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
                      className="text-xs h-7 px-2"
                    >
                      <Edit3 className="w-3 h-3 mr-1" />
                      Redraft
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="p-4 pt-2 space-y-2">
                  <div className="p-3 bg-muted/40 rounded-md text-xs font-mono text-slate-800 leading-relaxed">
                    {clause.raw_text}
                  </div>
                  {clause.risk_description && (
                    <div className="text-xs text-red-700 bg-red-50/60 p-2.5 rounded border border-red-200/60">
                      <strong>Risk:</strong> {clause.risk_description}
                    </div>
                  )}
                  {clause.legal_reasoning && (
                    <div className="text-xs text-slate-600 p-2.5 bg-slate-50 rounded border border-border">
                      <strong>Legal Analysis:</strong> {clause.legal_reasoning}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        {/* Tab 3: Full Document Text */}
        <TabsContent value="text">
          <Card className="shadow-sm">
            <CardContent className="p-6">
              <div className="contract-markdown markdown-body">
                <pre className="text-xs text-foreground whitespace-pre-wrap font-sans leading-relaxed">
                  {contract?.extracted_text || contract?.raw_text || analysis?.analysis_markdown || "Document text preview is not available."}
                </pre>
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
