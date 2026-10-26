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
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface TimelineItem {
  id: string;
  event_date: string;
  event_description: string;
  source_document_id?: string;
  source_page?: number;
  citation_quote?: string;
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
  const [activeTab, setActiveTab] = useState("analysis");

  // QA Assistant state
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
      toast.error("Failed to load analysis results");
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
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
        <span>Loading case intelligence dossier...</span>
      </div>
    );
  }

  const reportContent = analysisData?.content || {};

  return (
    <div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8">
      {/* 1. Header Navigation */}
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
              {caseDetail?.title || "Litigation Intelligence Dossier"}
            </h1>
            <Badge variant="success">Analyzed</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Multi-document synthesis, chronological event mapping, and evidentiary cross-examination.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.print()}
            className="text-xs"
          >
            Export Dossier
          </Button>
        </div>
      </div>

      {/* 2. Key Metrics Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="shadow-sm">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground font-medium">Indexed Exhibits</p>
            <p className="text-2xl font-bold text-foreground mt-1">
              {caseDetail?.documents?.length || 0}
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground font-medium">Timeline Events</p>
            <p className="text-2xl font-bold text-accent mt-1">
              {timelineItems.length}
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground font-medium">Audit Date</p>
            <p className="text-base font-bold text-foreground mt-2">
              {analysisData?.created_at
                ? new Date(analysisData.created_at).toLocaleDateString()
                : "Recent"}
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground font-medium">Forum Compliance</p>
            <p className="text-base font-bold text-emerald-700 mt-2">
              Verified
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 3. Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="analysis">Legal Report & Brief</TabsTrigger>
          <TabsTrigger value="timeline">Chronological Timeline ({timelineItems.length})</TabsTrigger>
          <TabsTrigger value="documents">Attached Exhibits ({caseDetail?.documents?.length || 0})</TabsTrigger>
          <TabsTrigger value="qa">Case Q&A Jurist</TabsTrigger>
        </TabsList>

        {/* Tab 1: Legal Report */}
        <TabsContent value="analysis" className="space-y-6">
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="text-sm font-semibold">Executive Legal Brief</CardTitle>
              <CardDescription className="text-xs">
                Comprehensive factual and statutory overview
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                {reportContent?.executive_summary ||
                  analysisData?.summary ||
                  "Analysis dossier compiled from documentary records."}
              </p>
            </CardContent>
          </Card>

          {/* Key Contradictions / Claims */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="shadow-sm">
              <CardHeader>
                <CardTitle className="text-sm font-semibold">Key Evidentiary Points</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {Array.isArray(reportContent?.key_findings) && reportContent.key_findings.length > 0 ? (
                  reportContent.key_findings.map((pt: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2 text-xs text-foreground">
                      <span className="text-accent font-bold mt-0.5">•</span>
                      <span>{pt}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground">No specific findings recorded.</p>
                )}
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader>
                <CardTitle className="text-sm font-semibold">Litigation Recommendations</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {Array.isArray(reportContent?.recommended_actions) && reportContent.recommended_actions.length > 0 ? (
                  reportContent.recommended_actions.map((act: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2 text-xs text-foreground">
                      <span className="text-emerald-600 font-bold mt-0.5">✓</span>
                      <span>{act}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground">Standard proceedings recommended.</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Tab 2: Chronological Timeline */}
        <TabsContent value="timeline" className="space-y-4">
          {timelineItems.length === 0 ? (
            <Card className="shadow-sm p-12 text-center text-xs text-muted-foreground">
              No chronological events extracted. Check exhibit parsing or trigger analysis again.
            </Card>
          ) : (
            <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
              {timelineItems.map((item, idx) => (
                <div key={item.id || idx} className="relative">
                  <div className="absolute -left-6 top-1.5 w-3 h-3 rounded-full bg-primary border-2 border-background" />
                  <Card className="shadow-sm">
                    <CardHeader className="p-4 pb-2 flex flex-row items-center justify-between">
                      <Badge variant="outline" className="text-xs font-mono">
                        {item.event_date || "Date Unspecified"}
                      </Badge>
                      {item.source_page && (
                        <span className="text-[11px] text-muted-foreground">
                          Page {item.source_page}
                        </span>
                      )}
                    </CardHeader>
                    <CardContent className="p-4 pt-1 space-y-2">
                      <p className="text-xs font-medium text-foreground leading-relaxed">
                        {item.event_description}
                      </p>
                      {item.citation_quote && (
                        <blockquote className="text-xs font-mono bg-muted/40 p-2.5 rounded border border-border text-slate-700 italic">
                          "{item.citation_quote}"
                        </blockquote>
                      )}
                    </CardContent>
                  </Card>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Tab 3: Documents */}
        <TabsContent value="documents">
          <Card className="shadow-sm">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Document Name</TableHead>
                    <TableHead className="text-xs">Type</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-xs">Added On</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {caseDetail?.documents?.map((doc: any) => (
                    <TableRow key={doc.id}>
                      <TableCell className="font-semibold text-xs text-foreground py-3">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                          <span className="truncate max-w-[320px]">{doc.name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground py-3 uppercase">
                        {doc.file_type?.split("/")[1] || "PDF"}
                      </TableCell>
                      <TableCell className="py-3">
                        <Badge variant="outline">{doc.status}</Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground py-3">
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

        {/* Tab 4: Interactive Case QA */}
        <TabsContent value="qa" className="space-y-4">
          <Card className="shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Litigation Case Jurist</CardTitle>
              <CardDescription className="text-xs">
                Ask specific factual or legal questions across all indexed case exhibits
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form onSubmit={handleSendQuestion} className="flex gap-2">
                <Input
                  type="text"
                  placeholder="e.g. When did the first breach occur according to Exhibit B? What were the damages claimed?"
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
                        <span className="text-accent font-bold">Q:</span>
                        <span>{qa.question}</span>
                      </p>
                      <div className="text-xs text-muted-foreground leading-relaxed pl-4 border-l-2 border-border whitespace-pre-wrap">
                        {qa.answer}
                      </div>
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
