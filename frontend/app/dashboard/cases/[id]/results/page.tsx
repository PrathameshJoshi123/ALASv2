"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Clock,
  FileText,
  Calendar,
  ShieldAlert,
  CheckCircle2,
  Send,
  MessageSquare,
  BookOpen,
  AlertCircle,
  Loader2,
  Scale,
  Gavel,
  Users,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Shield,
  FileWarning,
  ListChecks,
  AlertTriangle,
  FileCheck2,
  Scale as ScaleIcon,
  RefreshCw,
  Printer,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Markdown } from "@/components/ui/markdown";

interface TimelineItem {
  id?: string;
  event_date: string;
  event_description: string;
  source_document_id?: string;
  source_document_name?: string;
  source_page?: number;
  citation_quote?: string;
  event_type?: string;
  is_delay_or_gap?: boolean;
  delay_details?: string;
}

interface WitnessContradictionItem {
  witness_name: string;
  conflicting_party_or_record: string;
  defect_type: string;
  description: string;
  source_document_name?: string;
  source_page?: number;
  citation_quote?: string;
  impeachment_severity?: string;
  cross_examination_angle?: string;
}

interface ChargeIngredient {
  ingredient: string;
  evidentiary_support: string;
  citations?: string;
}

interface ChargeAnalysisItem {
  section: string;
  offence_name: string;
  statutory_act: string;
  ingredients: ChargeIngredient[];
  prosecution_strength?: string;
  defense_vulnerabilities?: string;
  defense_strategy?: string;
}

interface MissingEvidenceItem {
  item_name: string;
  legal_relevance: string;
  statutory_provision: string;
  severity: string;
  recommendation: string;
}

interface ProceduralComplianceItem {
  procedural_stage: string;
  requirement: string;
  statutory_deadline: string;
  status: string;
  remedy: string;
}

interface KanoonPrecedentItem {
  doc_id: string;
  title: string;
  court: string;
  year?: string;
  citation_standard: string;
  url: string;
  ratio_decidendi: string;
  statutory_sections?: string[];
  relevance: string;
  application_strategy?: string;
}

interface DocumentClassificationItem {
  document_id: string;
  document_name: string;
  classification: string;
  confidence?: number;
  rationale?: string;
  execution_or_filing_date?: string;
  citation_quote?: string;
  summary?: string;
  key_parties?: string[];
}

interface CaseDetail {
  id: string;
  title: string;
  description?: string;
  status: string;
  created_at: string;
  documents: any[];
}

export default function CaseResultsPage() {
  const router = useRouter();
  const routeParams = useParams();
  const caseId = routeParams?.id as string;

  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [timelineItems, setTimelineItems] = useState<TimelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("brief");

  // QA Jurist state
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [qaHistory, setQaHistory] = useState<
    { question: string; answer: string; citations?: any[] }[]
  >([]);

  const fetchResults = async () => {
    setLoading(true);
    try {
      const [cDetail, aData, tItems] = await Promise.allSettled([
        apiClient.getCaseDetails(caseId),
        apiClient.getCaseAnalysis(caseId),
        apiClient.getCaseTimeline(caseId),
      ]);

      if (cDetail.status === "fulfilled") setCaseDetail(cDetail.value);
      if (aData.status === "fulfilled") setAnalysisData(aData.value);
      if (tItems.status === "fulfilled") setTimelineItems(tItems.value || []);
    } catch (err: any) {
      console.error("Error fetching analysis results", err);
      toast.error("Failed to load case analysis dossier");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (caseId) {
      fetchResults();
    }
  }, [caseId]);

  const handleSendQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    const currentQ = question.trim();
    setQuestion("");
    setAsking(true);

    try {
      const res = await apiClient.askCaseQuestion(caseId, currentQ);
      setQaHistory((prev) => [
        ...prev,
        {
          question: currentQ,
          answer: res.answer || "No response received",
          citations: res.citations || [],
        },
      ]);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to get QA answer");
    } finally {
      setAsking(false);
    }
  };

  if (loading) {
    return (
      <div className="p-16 flex flex-col items-center justify-center text-xs text-muted-foreground gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-[#2563EB]" />
        <span>Loading comprehensive litigation intelligence dossier...</span>
      </div>
    );
  }

  const reportContent = analysisData?.content || {};
  const matterTitle = reportContent?.matter_title || caseDetail?.title || "Litigation Matter Intelligence Dossier";
  const executiveSummary = reportContent?.executive_summary || reportContent?.summary_report || analysisData?.summary || "Comprehensive legal brief compiled from documentary records.";
  const keyFindings: string[] = Array.isArray(reportContent?.key_findings) ? reportContent.key_findings : [];
  const recommendedActions: string[] = Array.isArray(reportContent?.recommended_actions) ? reportContent.recommended_actions : [];

  const documentClassifications: DocumentClassificationItem[] = Array.isArray(reportContent?.document_classifications) ? reportContent.document_classifications : [];
  const witnessContradictions: WitnessContradictionItem[] = Array.isArray(reportContent?.witness_contradictions) ? reportContent.witness_contradictions : [];
  const chargesAnalysis: ChargeAnalysisItem[] = Array.isArray(reportContent?.charges_analysis) ? reportContent.charges_analysis : [];
  const missingEvidence: MissingEvidenceItem[] = Array.isArray(reportContent?.missing_evidence) ? reportContent.missing_evidence : [];
  const proceduralCompliance: ProceduralComplianceItem[] = Array.isArray(reportContent?.procedural_compliance) ? reportContent.procedural_compliance : [];
  const kanoonPrecedents: KanoonPrecedentItem[] = Array.isArray(reportContent?.kanoon_precedents) ? reportContent.kanoon_precedents : [];

  // Master timeline combines DB records and extracted JSON
  const timelineDisplay: TimelineItem[] = timelineItems.length > 0 
    ? timelineItems 
    : (Array.isArray(reportContent?.timeline) ? reportContent.timeline : []);

  // Helper badge renderers
  const getSeverityBadge = (sev?: string) => {
    const s = (sev || "").toLowerCase();
    if (s === "critical" || s === "high") {
      return <Badge variant="destructive">{sev?.toUpperCase() || "HIGH"}</Badge>;
    }
    if (s === "medium" || s === "moderate") {
      return <Badge variant="warning">{sev?.toUpperCase() || "MEDIUM"}</Badge>;
    }
    return <Badge variant="outline">{sev?.toUpperCase() || "LOW"}</Badge>;
  };

  const getStrengthBadge = (strength?: string) => {
    const s = (strength || "").toLowerCase();
    if (s === "strong") {
      return <Badge variant="destructive">PROSECUTION STRONG</Badge>;
    }
    if (s === "moderate") {
      return <Badge variant="warning">MODERATE</Badge>;
    }
    return <Badge variant="success">PROSECUTION WEAK</Badge>;
  };

  const getComplianceStatusBadge = (status?: string) => {
    const s = (status || "").toLowerCase();
    if (s === "compliant") {
      return <Badge variant="success">COMPLIANT</Badge>;
    }
    if (s === "violated" || s === "overdue") {
      return <Badge variant="destructive">{status?.toUpperCase() || "VIOLATED"}</Badge>;
    }
    if (s === "pending") {
      return <Badge variant="info">PENDING</Badge>;
    }
    return <Badge variant="outline">{status?.toUpperCase() || "AUDITED"}</Badge>;
  };

  return (
    <div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <button
            onClick={() => router.push(`/dashboard/cases/${caseId}`)}
            className="inline-flex items-center text-xs font-semibold text-muted-foreground hover:text-foreground mb-2 gap-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Case Workspace</span>
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              {matterTitle}
            </h1>
            <Badge variant="success">Analyzed</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
            Multi-document synthesis, cross-examination contradictions, statutory ingredient auditing, and Indian Kanoon precedents.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchResults}
            className="text-xs gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.print()}
            className="text-xs gap-1.5"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Export Brief</span>
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={() => router.push(`/dashboard/cases/${caseId}/debate`)}
            className="text-xs gap-1.5 bg-[#2563EB] hover:bg-blue-700 text-white font-semibold"
          >
            <Gavel className="w-3.5 h-3.5" />
            <span>Pre-Trial War Room</span>
          </Button>
        </div>
      </div>

      {/* 2. Key Metrics Strip */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <Card className="shadow-sm">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Indexed Exhibits</p>
            <p className="text-xl font-bold text-foreground mt-1">
              {caseDetail?.documents?.length || documentClassifications.length || 0}
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Timeline Events</p>
            <p className="text-xl font-bold text-[#2563EB] mt-1">
              {timelineDisplay.length}
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Contradictions</p>
            <p className="text-xl font-bold text-red-600 mt-1">
              {witnessContradictions.length}
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Penal Charges</p>
            <p className="text-xl font-bold text-amber-700 mt-1">
              {chargesAnalysis.length}
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Evidence Gaps</p>
            <p className="text-xl font-bold text-slate-700 mt-1">
              {missingEvidence.length}
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-3.5">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Precedents</p>
            <p className="text-xl font-bold text-emerald-700 mt-1">
              {kanoonPrecedents.length}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 3. Comprehensive Master Navigation Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full flex flex-wrap h-auto gap-1 bg-muted/60 p-1.5 rounded-lg border border-border">
          <TabsTrigger value="brief" className="text-xs font-medium py-1.5 px-3">
            Executive Brief
          </TabsTrigger>
          <TabsTrigger value="timeline" className="text-xs font-medium py-1.5 px-3">
            Timeline & Delays ({timelineDisplay.length})
          </TabsTrigger>
          <TabsTrigger value="witnesses" className="text-xs font-medium py-1.5 px-3">
            Witness Contradictions ({witnessContradictions.length})
          </TabsTrigger>
          <TabsTrigger value="charges" className="text-xs font-medium py-1.5 px-3">
            Charges & Elements ({chargesAnalysis.length})
          </TabsTrigger>
          <TabsTrigger value="evidence" className="text-xs font-medium py-1.5 px-3">
            Evidentiary Gaps ({missingEvidence.length})
          </TabsTrigger>
          <TabsTrigger value="procedure" className="text-xs font-medium py-1.5 px-3">
            Procedural Audit ({proceduralCompliance.length})
          </TabsTrigger>
          <TabsTrigger value="precedents" className="text-xs font-medium py-1.5 px-3">
            Indian Kanoon ({kanoonPrecedents.length})
          </TabsTrigger>
          <TabsTrigger value="documents" className="text-xs font-medium py-1.5 px-3">
            Exhibits ({caseDetail?.documents?.length || 0})
          </TabsTrigger>
          <TabsTrigger value="qa" className="text-xs font-medium py-1.5 px-3">
            Jurist Q&A
          </TabsTrigger>
        </TabsList>

        {/* TAB 1: EXECUTIVE BRIEF */}
        <TabsContent value="brief" className="space-y-6 pt-4">
          <Card className="shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base font-semibold">Executive Legal Brief</CardTitle>
                  <CardDescription className="text-xs">
                    Synthesized litigation overview and prosecutorial vulnerability evaluation
                  </CardDescription>
                </div>
                <Badge variant="outline" className="font-mono text-[11px]">
                  Institutional Synthesis
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="bg-muted/20 p-4 rounded-md border border-border">
                <Markdown
                  content={executiveSummary}
                  className="text-xs sm:text-sm text-foreground leading-relaxed font-sans"
                />
              </div>
            </CardContent>
          </Card>

          {/* Key Findings & Tactical Recommendations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-red-600" />
                  <span>Key Evidentiary Findings</span>
                </CardTitle>
                <CardDescription className="text-xs">
                  Crucial evidentiary discrepancies and factual contradictions
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {keyFindings.length > 0 ? (
                  keyFindings.map((pt, idx) => (
                    <div key={idx} className="flex items-start gap-2.5 text-xs text-foreground bg-muted/30 p-2.5 rounded border border-border/60">
                      <span className="text-[#2563EB] font-bold mt-0.5">•</span>
                      <Markdown content={pt} className="leading-relaxed flex-1 text-xs" />
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground">No specific findings logged.</p>
                )}
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>Strategic Litigation Actions</span>
                </CardTitle>
                <CardDescription className="text-xs">
                  Tactical steps, applications, and procedural maneuvers for legal counsel
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {recommendedActions.length > 0 ? (
                  recommendedActions.map((act, idx) => (
                    <div key={idx} className="flex items-start gap-2.5 text-xs text-foreground bg-emerald-50/40 p-2.5 rounded border border-emerald-200/60">
                      <span className="text-emerald-700 font-bold mt-0.5">✓</span>
                      <Markdown content={act} className="leading-relaxed flex-1 text-xs" />
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground">Standard proceedings recommended.</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Document Classification Matrix */}
          {documentClassifications.length > 0 && (
            <Card className="shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <FileText className="w-4 h-4 text-slate-700" />
                  <span>Exhibit Classification & Authority Audit</span>
                </CardTitle>
                <CardDescription className="text-xs">
                  Legal categorization, filing dates, and verified source citations across all case records
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">Exhibit Name</TableHead>
                      <TableHead className="text-xs">Legal Category</TableHead>
                      <TableHead className="text-xs">Filing / Incident Date</TableHead>
                      <TableHead className="text-xs">Classification Rationale</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {documentClassifications.map((doc, idx) => (
                      <TableRow key={doc.document_id || idx}>
                        <TableCell className="font-semibold text-xs text-foreground py-3">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                            <span className="truncate max-w-[240px]">{doc.document_name}</span>
                          </div>
                        </TableCell>
                        <TableCell className="py-3">
                          <Badge variant="outline" className="font-mono text-[10px] bg-slate-50">
                            {doc.classification}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground py-3 font-mono">
                          {doc.execution_or_filing_date || "Date Unspecified"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground py-3 max-w-[340px]">
                          <Markdown content={doc.rationale || doc.citation_quote || "Identified from document header."} inline className="truncate" />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* TAB 2: CHRONOLOGY & DELAYS */}
        <TabsContent value="timeline" className="space-y-6 pt-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">Chronological Master Timeline & Delay Audit</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Exact sequence of occurrences, filings, medical exams, and flagged investigative delays.
              </p>
            </div>
            <Badge variant="outline" className="font-mono text-xs">
              {timelineDisplay.length} Sequential Events
            </Badge>
          </div>

          {timelineDisplay.length === 0 ? (
            <Card className="shadow-sm p-12 text-center text-xs text-muted-foreground">
              No chronological events extracted. Check exhibit parsing or trigger analysis again.
            </Card>
          ) : (
            <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
              {timelineDisplay.map((item, idx) => (
                <div key={item.id || idx} className="relative">
                  <div className="absolute -left-6 top-2 w-3 h-3 rounded-full bg-[#2563EB] border-2 border-background" />
                  <Card className="shadow-sm">
                    <CardHeader className="p-4 pb-2 flex flex-row items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs font-mono bg-muted/30">
                          {item.event_date || "Date Unspecified"}
                        </Badge>
                        {item.event_type && (
                          <Badge variant="secondary" className="text-[10px] uppercase font-mono">
                            {item.event_type.replace(/_/g, " ")}
                          </Badge>
                        )}
                        {item.is_delay_or_gap && (
                          <Badge variant="destructive" className="text-[10px]">
                            Investigative Delay
                          </Badge>
                        )}
                      </div>
                      {(item.source_page || item.source_document_name) && (
                        <span className="text-[11px] text-muted-foreground font-mono">
                          {item.source_document_name ? `${item.source_document_name} ` : ""}
                          {item.source_page ? `(Page ${item.source_page})` : ""}
                        </span>
                      )}
                    </CardHeader>
                    <CardContent className="p-4 pt-1 space-y-2">
                      <Markdown content={item.event_description} className="text-xs font-medium text-foreground leading-relaxed" />
                      {item.delay_details && (
                        <div className="text-xs text-red-700 bg-red-50 p-2 rounded border border-red-200 space-y-1">
                          <strong className="block text-red-900">Delay Analysis:</strong>
                          <Markdown content={item.delay_details} className="text-xs text-red-700" />
                        </div>
                      )}
                      {item.citation_quote && (
                        <div className="text-xs font-mono bg-muted/40 p-2.5 rounded border border-border text-slate-700 italic">
                          <Markdown content={item.citation_quote} className="text-xs font-mono" />
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* TAB 3: WITNESS CONTRADICTIONS & IMPEACHMENT */}
        <TabsContent value="witnesses" className="space-y-6 pt-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">Witness Testimony & Impeachment Matrix</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Section 161/164 CrPC/BNSS discrepancies, material omissions, and physical evidence conflicts.
              </p>
            </div>
            <Badge variant="destructive" className="text-xs">
              {witnessContradictions.length} Contradictions Detected
            </Badge>
          </div>

          {witnessContradictions.length === 0 ? (
            <Card className="shadow-sm p-12 text-center text-xs text-muted-foreground">
              No direct witness testimony contradictions or material omissions flagged across records.
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {witnessContradictions.map((wc, idx) => (
                <Card key={idx} className="shadow-sm border-l-4 border-l-red-500">
                  <CardHeader className="p-4 pb-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-foreground">
                        {wc.witness_name}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <Badge variant="outline" className="text-[10px] font-mono bg-red-50 text-red-700 border-red-200">
                          {wc.defect_type || "Contradiction"}
                        </Badge>
                        {getSeverityBadge(wc.impeachment_severity)}
                      </div>
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      Conflicts with: <strong className="text-slate-800">{wc.conflicting_party_or_record}</strong>
                    </p>
                  </CardHeader>
                  <CardContent className="p-4 pt-1 space-y-3">
                    <Markdown content={wc.description} className="text-xs text-foreground leading-relaxed" />

                    {wc.citation_quote && (
                      <div className="space-y-1">
                        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                          Verified Citation ({wc.source_document_name || "Exhibit"} {wc.source_page ? `Page ${wc.source_page}` : ""}):
                        </p>
                        <div className="text-[11px] font-mono bg-muted/40 p-2 rounded border border-border text-slate-800 italic">
                          <Markdown content={wc.citation_quote} className="text-[11px] font-mono" />
                        </div>
                      </div>
                    )}

                    {wc.cross_examination_angle && (
                      <div className="bg-blue-50/60 p-2.5 rounded border border-blue-200 text-xs space-y-1">
                        <p className="text-[10px] font-bold text-blue-900 uppercase tracking-wider flex items-center gap-1">
                          <Gavel className="w-3 h-3 text-[#2563EB]" />
                          <span>Cross-Examination Tactical Line (Sec 145/146 Evidence Act / BSA):</span>
                        </p>
                        <Markdown content={wc.cross_examination_angle} className="text-[11px] text-blue-950 leading-relaxed" />
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* TAB 4: CHARGES & INGREDIENTS AUDIT */}
        <TabsContent value="charges" className="space-y-6 pt-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">Statutory Penal Charges & Ingredients Audit</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                IPC / BNS statutory provisions broken down into statutory elements against evidentiary support.
              </p>
            </div>
            <Badge variant="outline" className="font-mono text-xs">
              {chargesAnalysis.length} Sections Audited
            </Badge>
          </div>

          {chargesAnalysis.length === 0 ? (
            <Card className="shadow-sm p-12 text-center text-xs text-muted-foreground">
              No statutory charges audited. Please ensure exhibits contain the FIR or charge sheet.
            </Card>
          ) : (
            <div className="space-y-6">
              {chargesAnalysis.map((ch, idx) => (
                <Card key={idx} className="shadow-sm">
                  <CardHeader className="p-4 pb-3 border-b border-border bg-muted/20">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold text-foreground">
                            {ch.section}
                          </h3>
                          <Badge variant="outline" className="text-[10px] font-mono bg-slate-50">
                            {ch.statutory_act || "IPC / BNS"}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {ch.offence_name}
                        </p>
                      </div>
                      <div>
                        {getStrengthBadge(ch.prosecution_strength)}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="p-4 space-y-4">
                    {/* Ingredients Table */}
                    {Array.isArray(ch.ingredients) && ch.ingredients.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-[11px] font-bold text-foreground uppercase tracking-wider">
                          Statutory Ingredients & Evidence Mapping:
                        </p>
                        <div className="border border-border rounded-md overflow-hidden">
                          <Table>
                            <TableHeader>
                              <TableRow className="bg-muted/40">
                                <TableHead className="text-xs w-[35%]">Legal Element / Ingredient</TableHead>
                                <TableHead className="text-xs w-[40%]">Evidentiary Support</TableHead>
                                <TableHead className="text-xs w-[25%]">Citation</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {ch.ingredients.map((ing, iIdx) => {
                                const isSupported = (ing.evidentiary_support || "").toLowerCase().includes("backed");
                                return (
                                  <TableRow key={iIdx}>
                                    <TableCell className="text-xs font-medium text-foreground py-2.5">
                                      <Markdown content={ing.ingredient} inline />
                                    </TableCell>
                                    <TableCell className="text-xs py-2.5">
                                      <div className="flex items-center gap-1.5">
                                        <span className={`w-2 h-2 rounded-full ${isSupported ? 'bg-emerald-500' : 'bg-red-500'}`} />
                                        <Markdown
                                          content={ing.evidentiary_support}
                                          inline
                                          className={isSupported ? 'text-emerald-800' : 'text-red-700 font-medium'}
                                        />
                                      </div>
                                    </TableCell>
                                    <TableCell className="text-xs text-muted-foreground font-mono py-2.5">
                                      {ing.citations || "Not cited"}
                                    </TableCell>
                                  </TableRow>
                                );
                              })}
                            </TableBody>
                          </Table>
                        </div>
                      </div>
                    )}

                    {/* Defense Vulnerabilities & Strategy */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                      {ch.defense_vulnerabilities && (
                        <div className="p-3 rounded bg-red-50/50 border border-red-200 text-xs space-y-1">
                          <p className="font-bold text-red-900 text-[10px] uppercase tracking-wider">
                            Prosecution Flaws & Missing Proof:
                          </p>
                          <Markdown content={ch.defense_vulnerabilities} className="text-red-950 leading-relaxed text-xs" />
                        </div>
                      )}
                      {ch.defense_strategy && (
                        <div className="p-3 rounded bg-emerald-50/50 border border-emerald-200 text-xs space-y-1">
                          <p className="font-bold text-emerald-900 text-[10px] uppercase tracking-wider">
                            Defense Legal Counter-Theory:
                          </p>
                          <Markdown content={ch.defense_strategy} className="text-emerald-950 leading-relaxed text-xs" />
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* TAB 5: EVIDENTIARY GAPS & MISSING EVIDENCE */}
        <TabsContent value="evidence" className="space-y-6 pt-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">Evidentiary Gaps & Missing Statutory Records</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Audit of absent certificates under Section 65B/63 BSA, forensic reports, and seizure panchanamas.
              </p>
            </div>
            <Badge variant="destructive" className="text-xs font-mono">
              {missingEvidence.length} Evidentiary Defects
            </Badge>
          </div>

          {missingEvidence.length === 0 ? (
            <Card className="shadow-sm p-12 text-center text-xs text-muted-foreground">
              No mandatory evidentiary records or certificates flagged as missing.
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {missingEvidence.map((me, idx) => (
                <Card key={idx} className="shadow-sm">
                  <CardHeader className="p-4 pb-2 flex flex-row items-start justify-between gap-2">
                    <div>
                      <CardTitle className="text-xs font-bold text-foreground">
                        {me.item_name}
                      </CardTitle>
                      <span className="text-[11px] font-mono text-muted-foreground">
                        {me.statutory_provision || "Statutory Requirement"}
                      </span>
                    </div>
                    {getSeverityBadge(me.severity)}
                  </CardHeader>
                  <CardContent className="p-4 pt-1 space-y-3">
                    <div className="space-y-1">
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Legal Justification:</p>
                      <Markdown content={me.legal_relevance} className="text-xs text-foreground leading-relaxed" />
                    </div>

                    {me.recommendation && (
                      <div className="p-2.5 rounded bg-muted/40 border border-border text-xs space-y-1">
                        <p className="text-[10px] font-bold text-slate-800 uppercase tracking-wider">
                          Strategic Counsel Recommendation:
                        </p>
                        <Markdown content={me.recommendation} className="text-slate-700 leading-relaxed text-xs" />
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* TAB 6: PROCEDURAL AUDIT & DEADLINES */}
        <TabsContent value="procedure" className="space-y-6 pt-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">Procedural Compliance & Statutory Deadlines</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Procedural stage audit, default bail windows under 167(2) CrPC / 187 BNSS, and limitation periods.
              </p>
            </div>
            <Badge variant="outline" className="font-mono text-xs">
              {proceduralCompliance.length} Checkpoints
            </Badge>
          </div>

          {proceduralCompliance.length === 0 ? (
            <Card className="shadow-sm p-12 text-center text-xs text-muted-foreground">
              No specific procedural compliance checkpoints tracked.
            </Card>
          ) : (
            <div className="space-y-4">
              {proceduralCompliance.map((pc, idx) => (
                <Card key={idx} className="shadow-sm">
                  <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="text-[10px] uppercase font-mono">
                          {pc.procedural_stage || "Stage"}
                        </Badge>
                        <span className="text-xs font-bold text-foreground">
                          <Markdown content={pc.requirement} inline />
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Statutory Deadline / Period: <strong className="text-slate-800 font-mono">{pc.statutory_deadline || "Not specified"}</strong>
                      </p>
                      {pc.remedy && (
                        <div className="text-xs text-blue-900 bg-blue-50/50 p-2 rounded border border-blue-200 space-y-1">
                          <strong className="block text-blue-950">Remedy / Application:</strong>
                          <Markdown content={pc.remedy} className="text-xs text-blue-900" />
                        </div>
                      )}
                    </div>
                    <div className="shrink-0">
                      {getComplianceStatusBadge(pc.status)}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* TAB 7: INDIAN KANOON PRECEDENTS */}
        <TabsContent value="precedents" className="space-y-6 pt-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">Indian Kanoon Precedents & Legal Authorities</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Landmark Supreme Court and High Court precedents retrieved live from indiankanoon.org.
              </p>
            </div>
            <Badge variant="outline" className="font-mono text-xs">
              {kanoonPrecedents.length} Landmark Judgments
            </Badge>
          </div>

          {kanoonPrecedents.length === 0 ? (
            <Card className="shadow-sm p-12 text-center text-xs text-muted-foreground">
              No Indian Kanoon precedents retrieved for this matter yet.
            </Card>
          ) : (
            <div className="space-y-4">
              {kanoonPrecedents.map((prec, idx) => (
                <Card key={idx} className="shadow-sm border-l-4 border-l-[#2563EB]">
                  <CardHeader className="p-4 pb-2">
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                      <div>
                        <CardTitle className="text-sm font-bold text-foreground flex items-center gap-2">
                          <ScaleIcon className="w-4 h-4 text-[#2563EB]" />
                          <span>{prec.title}</span>
                        </CardTitle>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs font-semibold text-slate-700">{prec.court}</span>
                          {prec.year && <span className="text-xs text-muted-foreground font-mono">({prec.year})</span>}
                          <Badge variant="outline" className="text-[10px] font-mono bg-slate-50">
                            {prec.citation_standard || "Standard Citation"}
                          </Badge>
                        </div>
                      </div>
                      {prec.url && (
                        <a
                          href={prec.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center text-xs font-semibold text-[#2563EB] hover:underline gap-1 shrink-0"
                        >
                          <span>Inspect on Indian Kanoon</span>
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="p-4 pt-2 space-y-3">
                    {/* Ratio Decidendi */}
                    <div className="p-3 rounded bg-blue-50/50 border border-blue-200 text-xs space-y-1">
                      <p className="text-[10px] font-bold text-blue-900 uppercase tracking-wider">
                        Binding Ratio Decidendi:
                      </p>
                      <Markdown content={prec.ratio_decidendi} className="text-blue-950 leading-relaxed text-xs" />
                    </div>

                    {/* Statutory Sections */}
                    {Array.isArray(prec.statutory_sections) && prec.statutory_sections.length > 0 && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-[10px] font-semibold text-muted-foreground uppercase">Provisions:</span>
                        {prec.statutory_sections.map((sec, sIdx) => (
                          <Badge key={sIdx} variant="secondary" className="text-[10px] font-mono">
                            {sec}
                          </Badge>
                        ))}
                      </div>
                    )}

                    {/* Strategic Relevance */}
                    <div className="text-xs space-y-1">
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                        Relevance to Current Matter:
                      </p>
                      <Markdown content={prec.relevance} className="text-foreground leading-relaxed text-xs" />
                    </div>

                    {/* Application Strategy */}
                    {prec.application_strategy && (
                      <div className="text-xs space-y-1">
                        <p className="text-[10px] font-bold text-emerald-800 uppercase tracking-wider">
                          Tactical Deployment in Argument:
                        </p>
                        <Markdown content={prec.application_strategy} className="text-slate-700 leading-relaxed text-xs" />
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* TAB 8: ATTACHED EXHIBITS */}
        <TabsContent value="documents" className="space-y-6 pt-4">
          <Card className="shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Indexed Case Exhibits & Filings</CardTitle>
              <CardDescription className="text-xs">
                Exhibits ingested, OCR analyzed, and chunked into the case knowledge graph
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Document Name</TableHead>
                    <TableHead className="text-xs">Legal Classification</TableHead>
                    <TableHead className="text-xs">Format</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-xs">Uploaded Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {caseDetail?.documents?.map((doc: any) => (
                    <TableRow key={doc.id}>
                      <TableCell className="font-semibold text-xs text-foreground py-3">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                          <span className="truncate max-w-[300px]">{doc.name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="py-3">
                        <Badge variant="outline" className="font-mono text-[10px] bg-slate-50">
                          {doc.document_type || "Unclassified"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground py-3 uppercase">
                        {doc.file_type?.split("/")[1] || "PDF"}
                      </TableCell>
                      <TableCell className="py-3">
                        <Badge variant="outline">{doc.status}</Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground py-3 font-mono">
                        {doc.date_created
                          ? new Date(doc.date_created).toLocaleDateString()
                          : "Recently"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 9: JURIST Q&A */}
        <TabsContent value="qa" className="space-y-6 pt-4">
          <Card className="shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Litigation Case Jurist</CardTitle>
              <CardDescription className="text-xs">
                Ask specific factual or legal questions across all indexed case exhibits with grounded citations
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form onSubmit={handleSendQuestion} className="flex gap-2">
                <Input
                  type="text"
                  placeholder="e.g. When did the first confrontation occur according to PW-1? Are Section 65B certificates attached?"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  className="text-xs h-9 flex-1"
                />
                <Button
                  type="submit"
                  size="sm"
                  loading={asking}
                  disabled={!question.trim() || asking}
                  className="text-xs"
                >
                  <Send className="w-3.5 h-3.5 mr-1" />
                  Ask
                </Button>
              </form>

              {qaHistory.length > 0 && (
                <div className="space-y-3 pt-2">
                  {qaHistory.map((qa, i) => (
                    <div key={i} className="p-3.5 rounded-md border border-border bg-card space-y-2">
                      <p className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                        <span className="text-[#2563EB] font-bold">Q:</span>
                        <span>{qa.question}</span>
                      </p>
                      <div className="text-xs text-foreground/90 leading-relaxed pl-4 border-l-2 border-border">
                        <Markdown content={qa.answer} className="text-xs text-foreground/90" />
                      </div>
                      {qa.citations && qa.citations.length > 0 && (
                        <div className="pl-4 pt-1 flex flex-wrap gap-1.5">
                          {qa.citations.map((c, ci) => (
                            <Badge key={ci} variant="outline" className="text-[10px] font-mono">
                              {c.document_name || "Doc"} {c.page ? `(p. ${c.page})` : ""}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
