"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { 
  ArrowLeft, Sparkles, Clock, FileText, Calendar, ShieldAlert, 
  CheckCircle2, Send, MessageSquare, BookOpen, AlertCircle, Loader2, Download,
  Scale, Gavel, Users, AlertTriangle, ChevronDown, ChevronUp, FileCheck
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";

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
  const routeParams = useParams();
  const caseId = routeParams?.id as string;

  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [timelineItems, setTimelineItems] = useState<TimelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showRawJson, setShowRawJson] = useState(false);

  // Active Tab
  const [activeTab, setActiveTab] = useState<"analysis" | "timeline" | "documents" | "qa">("analysis");

  // QA Assistant state
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [qaHistory, setQaHistory] = useState<{ question: string; answer: string; citations?: any[] }[]>([]);

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
    fetchResults();
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
      <div className="flex items-center justify-center py-30">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        <span className="ml-3 text-slate-600 font-medium">Loading DB analysis results...</span>
      </div>
    );
  }

  const reportContent = analysisData?.content || {};

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Top Breadcrumb Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href={`/dashboard/cases/${caseId}`}
          className="text-slate-500 hover:text-slate-900 text-sm font-semibold inline-flex items-center gap-1.5 transition"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Case Workspace
        </Link>
      </div>

      {/* Header Banner */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-indigo-600" />
              </div>
              <h1 className="text-2xl font-bold text-slate-900">
                {caseDetail?.title || "Case Analysis Results"}
              </h1>
            </div>
            <p className="text-sm text-slate-500">
              Multi-agent compiled report fetched directly from the database.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className="px-3 py-1.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 inline-flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" /> Analyzed from DB
            </span>
          </div>
        </div>

        {/* Metrics Row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-3 border-t border-slate-100">
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
            <p className="text-xs text-slate-400 font-semibold">Attached Documents</p>
            <p className="text-lg font-bold text-slate-800">{caseDetail?.documents?.length || 0}</p>
          </div>
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
            <p className="text-xs text-slate-400 font-semibold">Timeline Events</p>
            <p className="text-lg font-bold text-indigo-600">{timelineItems.length}</p>
          </div>
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
            <p className="text-xs text-slate-400 font-semibold">Analysis Date</p>
            <p className="text-sm font-bold text-slate-800">
              {analysisData?.created_at
                ? new Date(analysisData.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })
                : "Recent"}
            </p>
          </div>
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
            <p className="text-xs text-slate-400 font-semibold">Case Status</p>
            <p className="text-sm font-bold text-emerald-700 uppercase">Analyzed</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 gap-6">
        <button
          onClick={() => setActiveTab("analysis")}
          className={`pb-3 text-sm font-bold flex items-center gap-2 transition border-b-2 ${
            activeTab === "analysis"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-900"
          }`}
        >
          <BookOpen className="w-4 h-4" />
          Legal Report & Analysis
        </button>

        <button
          onClick={() => setActiveTab("timeline")}
          className={`pb-3 text-sm font-bold flex items-center gap-2 transition border-b-2 ${
            activeTab === "timeline"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-900"
          }`}
        >
          <Clock className="w-4 h-4" />
          Chronological Timeline ({timelineItems.length})
        </button>

        <button
          onClick={() => setActiveTab("documents")}
          className={`pb-3 text-sm font-bold flex items-center gap-2 transition border-b-2 ${
            activeTab === "documents"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-900"
          }`}
        >
          <FileText className="w-4 h-4" />
          Documents ({caseDetail?.documents?.length || 0})
        </button>

        <button
          onClick={() => setActiveTab("qa")}
          className={`pb-3 text-sm font-bold flex items-center gap-2 transition border-b-2 ${
            activeTab === "qa"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-900"
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          Interactive Case QA
        </button>
      </div>

      {/* Tab 1: Executive Report & Legal Analysis */}
      {activeTab === "analysis" && (
        <div className="space-y-6">
          {!analysisData ? (
            <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center text-slate-400">
              <AlertCircle className="w-8 h-8 text-amber-500 mx-auto mb-2" />
              <p>No compiled analysis report found in DB yet.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Executive Summary & Case Strength Banner */}
              <div className="bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 text-white shadow-md space-y-4 border border-slate-800">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center shrink-0">
                      <Sparkles className="w-5 h-5 text-indigo-400" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-slate-100">Executive Legal Brief</h3>
                      <p className="text-xs text-slate-400">Multi-agent deep case analysis synthesis</p>
                    </div>
                  </div>

                  {reportContent.overall_risk_score !== undefined && (
                    <div className="flex items-center gap-2 bg-slate-800/80 border border-slate-700 px-4 py-2 rounded-xl shrink-0">
                      <span className="text-xs text-slate-400 uppercase font-mono font-semibold">Case Strength / Risk:</span>
                      <span className="text-base font-bold text-amber-400 font-mono">
                        {reportContent.overall_risk_score}%
                      </span>
                    </div>
                  )}
                </div>

                {(reportContent.summary_report || reportContent.summary || reportContent.executive_summary) && (
                  <p className="text-sm text-slate-300 leading-relaxed font-normal">
                    {reportContent.summary_report || reportContent.summary || reportContent.executive_summary}
                  </p>
                )}
              </div>

              {/* Document Classifications */}
              {Array.isArray(reportContent.document_classifications) && reportContent.document_classifications.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-4">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
                    <FileCheck className="w-5 h-5 text-indigo-600" />
                    Document Schema Classifications ({reportContent.document_classifications.length})
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {reportContent.document_classifications.map((doc: any, idx: number) => (
                      <div key={idx} className="p-4 bg-slate-50 rounded-xl border border-slate-200/70 space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="font-bold text-slate-900 text-sm truncate">{doc.name}</h4>
                          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase bg-indigo-100 text-indigo-800 shrink-0">
                            {doc.category || "DOCUMENT"}
                          </span>
                        </div>
                        {doc.rationale && (
                          <p className="text-xs text-slate-600 leading-relaxed">{doc.rationale}</p>
                        )}
                        {doc.citation && (
                          <span className="inline-block text-[10px] font-mono text-slate-500 bg-white px-2 py-1 rounded border border-slate-200">
                            {doc.citation}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Statutory Charges & IPC/BNSS Elements Analysis */}
              {Array.isArray(reportContent.charges_analysis) && reportContent.charges_analysis.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-4">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
                    <Scale className="w-5 h-5 text-indigo-600" />
                    Statutory Charges & Ingredients Mapping
                  </h3>

                  <div className="space-y-4">
                    {reportContent.charges_analysis.map((charge: any, idx: number) => (
                      <div key={idx} className="p-5 bg-slate-50/70 rounded-xl border border-slate-200/80 space-y-3">
                        <div className="flex items-center justify-between gap-2 border-b border-slate-200/60 pb-2">
                          <h4 className="font-bold text-slate-900 text-sm">
                            {charge.offence_name || charge.offense_name || `Offense ${idx + 1}`}
                          </h4>
                          <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-amber-100 text-amber-900 border border-amber-200">
                            {charge.section || charge.statutory_section || "BNS / IPC"}
                          </span>
                        </div>

                        {(charge.ingredients || charge.statutory_elements) && (
                          <div className="text-xs text-slate-700 bg-white p-3 rounded-lg border border-slate-200/60">
                            <span className="font-bold text-slate-900">Statutory Ingredients: </span>
                            {Array.isArray(charge.ingredients || charge.statutory_elements)
                              ? (charge.ingredients || charge.statutory_elements).join(", ")
                              : charge.ingredients || charge.statutory_elements}
                          </div>
                        )}

                        {(charge.evidence_status || charge.prosecution_evidence || charge.defense_vulnerabilities) && (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                            {(charge.evidence_status || charge.prosecution_evidence) && (
                              <div className="p-3 bg-emerald-50/60 border border-emerald-200/80 rounded-lg text-xs space-y-1">
                                <span className="font-bold text-emerald-900 uppercase tracking-wider text-[10px]">Evidentiary Status & Support</span>
                                <p className="text-slate-800">{charge.evidence_status || charge.prosecution_evidence}</p>
                              </div>
                            )}
                            {charge.defense_vulnerabilities && (
                              <div className="p-3 bg-rose-50/60 border border-rose-200/80 rounded-lg text-xs space-y-1">
                                <span className="font-bold text-rose-900 uppercase tracking-wider text-[10px]">Defense Vulnerabilities</span>
                                <p className="text-slate-800">{charge.defense_vulnerabilities}</p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Witness Testimonial Contradictions */}
              {Array.isArray(reportContent.witness_contradictions) && reportContent.witness_contradictions.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-4">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
                    <Users className="w-5 h-5 text-indigo-600" />
                    Witness Contradictions & Statements
                  </h3>

                  <div className="space-y-4">
                    {reportContent.witness_contradictions.map((wit: any, idx: number) => (
                      <div key={idx} className="p-5 bg-slate-50/70 rounded-xl border border-slate-200/80 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-indigo-900 text-sm">
                            {wit.witness_1 && wit.witness_2
                              ? `${wit.witness_1} vs ${wit.witness_2}`
                              : wit.witness_name || wit.witness_1 || `Witness ${idx + 1}`}
                          </span>
                          <span className="text-xs text-rose-600 font-bold bg-rose-50 border border-rose-200 px-2.5 py-0.5 rounded-full">
                            {wit.finding_type || "CONTRADICTION"}
                          </span>
                        </div>

                        {(wit.details || wit.claimed_statement || wit.conflicting_evidence) && (
                          <div className="p-3.5 bg-white border border-slate-200 rounded-lg text-xs space-y-2">
                            {wit.details && (
                              <p className="text-slate-800 leading-relaxed">
                                <strong className="text-slate-900">Finding Details: </strong>
                                {wit.details}
                              </p>
                            )}
                            {wit.claimed_statement && (
                              <p className="text-slate-800 italic">
                                <strong className="text-slate-900 not-italic">Claimed Statement: </strong>
                                &quot;{wit.claimed_statement}&quot;
                              </p>
                            )}
                            {wit.conflicting_evidence && (
                              <p className="text-amber-900 bg-amber-50/70 p-2 rounded border border-amber-200/80">
                                <strong>Conflicting Evidence: </strong> {wit.conflicting_evidence}
                              </p>
                            )}
                          </div>
                        )}

                        {wit.cross_exam_strategy && (
                          <div className="p-3 bg-indigo-50/60 border border-indigo-200/80 rounded-lg text-xs space-y-1">
                            <span className="font-bold text-indigo-900 uppercase tracking-wider text-[10px]">Cross-Examination Defense Strategy</span>
                            <p className="text-slate-800">{wit.cross_exam_strategy}</p>
                          </div>
                        )}

                        {wit.citation && (
                          <span className="inline-block text-[10px] font-mono text-slate-500 bg-white px-2 py-1 rounded border border-slate-200">
                            {wit.citation}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Procedural Compliance Tracker */}
              {Array.isArray(reportContent.procedural_compliance) && reportContent.procedural_compliance.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-4">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
                    <CheckCircle2 className="w-5 h-5 text-indigo-600" />
                    Procedural Compliance Checklist
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {reportContent.procedural_compliance.map((comp: any, idx: number) => (
                      <div key={idx} className="p-4 bg-slate-50 rounded-xl border border-slate-200/70 space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-bold text-slate-900 text-xs">{comp.stage || comp.legal_stage || `Stage ${idx + 1}`}</span>
                          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                            comp.status?.includes("COMPLIED") ? "bg-emerald-100 text-emerald-800 border border-emerald-200" : comp.status?.includes("VIOLATION") ? "bg-rose-100 text-rose-800 border border-rose-200" : "bg-amber-100 text-amber-800 border border-amber-200"
                          }`}>
                            {comp.status || "CHECKED"}
                          </span>
                        </div>
                        {(comp.statutory_reference || comp.mandated_procedure) && (
                          <p className="text-xs text-slate-600 font-mono bg-white p-2 rounded border border-slate-200/60">
                            {comp.statutory_reference || comp.mandated_procedure}
                          </p>
                        )}
                        {comp.legal_impact && (
                          <p className="text-xs text-indigo-900 bg-indigo-50/70 p-2 rounded border border-indigo-100">
                            <strong>Impact:</strong> {comp.legal_impact}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Indian Kanoon Precedents */}
              {Array.isArray(reportContent.kanoon_precedents) && reportContent.kanoon_precedents.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-4">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
                    <Gavel className="w-5 h-5 text-indigo-600" />
                    Judicial Precedents & Legal Ratios (Indian Kanoon)
                  </h3>

                  <div className="space-y-3">
                    {reportContent.kanoon_precedents.map((prec: any, idx: number) => (
                      <div key={idx} className="p-4 bg-slate-50 rounded-xl border border-slate-200/70 space-y-2 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-indigo-900 font-mono">{prec.citation}</span>
                          <span className="text-[10px] font-bold uppercase bg-slate-200 text-slate-700 px-2 py-0.5 rounded">Precedent</span>
                        </div>
                        {prec.key_ratio && <p className="text-slate-800"><strong>Key Ratio:</strong> {prec.key_ratio}</p>}
                        {prec.relevance && <p className="text-slate-600"><strong>Application:</strong> {prec.relevance}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Missing Evidence & Gaps */}
              {Array.isArray(reportContent.missing_evidence) && reportContent.missing_evidence.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-4">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
                    <AlertTriangle className="w-5 h-5 text-rose-600" />
                    Investigation Gaps & Missing Evidence ({reportContent.missing_evidence.length})
                  </h3>

                  <div className="space-y-3">
                    {reportContent.missing_evidence.map((gap: any, idx: number) => (
                      <div key={idx} className="p-4 bg-rose-50/50 border border-rose-200/80 rounded-xl space-y-2 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-900">{gap.missing_item || `Item ${idx + 1}`}</span>
                          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase bg-rose-200 text-rose-900">
                            {gap.severity || gap.risk_level || "RISK"}
                          </span>
                        </div>
                        {gap.relevance && (
                          <p className="text-slate-700 leading-relaxed"><strong>Relevance:</strong> {gap.relevance}</p>
                        )}
                        {gap.recommended_action && (
                          <p className="text-slate-800 font-semibold"><strong>Action Required:</strong> {gap.recommended_action}</p>
                        )}
                        {gap.citation && (
                          <span className="inline-block text-[10px] font-mono text-slate-500 bg-white px-2 py-1 rounded border border-slate-200">
                            {gap.citation}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Optional Collapsible Raw JSON Viewer for Inspection */}
              <div className="pt-4 border-t border-slate-200">
                <button
                  onClick={() => setShowRawJson(!showRawJson)}
                  className="text-xs text-slate-500 hover:text-slate-900 font-semibold inline-flex items-center gap-1 transition"
                >
                  {showRawJson ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  {showRawJson ? "Hide Raw Agent JSON Output" : "View Raw Agent JSON Output"}
                </button>

                {showRawJson && (
                  <div className="mt-3 p-4 bg-slate-900 text-slate-100 font-mono text-xs rounded-xl overflow-x-auto whitespace-pre-wrap">
                    {typeof reportContent === "string" ? reportContent : JSON.stringify(reportContent, null, 2)}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Chronological Timeline */}
      {activeTab === "timeline" && (
        <div className="bg-white rounded-2xl border border-slate-200/80 p-8 shadow-xs space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <h3 className="font-bold text-slate-900 text-lg flex items-center gap-2">
              <Clock className="w-5 h-5 text-indigo-600" />
              Chronological Case Events
            </h3>
            <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1 rounded-full">
              {timelineItems.length} Extracted Events
            </span>
          </div>

          {timelineItems.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-sm">
              No timeline events extracted yet for this case.
            </div>
          ) : (
            <div className="relative border-l-2 border-indigo-200 ml-4 space-y-8 py-2">
              {timelineItems.map((item, idx) => (
                <div key={item.id || idx} className="relative pl-6 group">
                  <div className="absolute -left-[9px] top-1.5 w-4 h-4 rounded-full bg-white border-4 border-indigo-600 group-hover:scale-125 transition" />
                  
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-2 shadow-2xs hover:shadow-xs transition">
                    <div className="flex items-center justify-between gap-2">
                      <span className="inline-flex items-center gap-1 text-xs font-bold text-indigo-700 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-100">
                        <Calendar className="w-3 h-3" />
                        {new Date(item.event_date).toLocaleDateString(undefined, { dateStyle: "long" })}
                      </span>
                      {item.source_page && (
                        <span className="text-xs font-semibold text-slate-500">
                          Page {item.source_page}
                        </span>
                      )}
                    </div>

                    <p className="font-medium text-slate-900 text-sm leading-relaxed">
                      {item.event_description}
                    </p>

                    {item.citation_quote && (
                      <div className="mt-2 text-xs italic text-slate-600 bg-white p-2.5 rounded-lg border border-slate-200/60">
                        &quot;{item.citation_quote}&quot;
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Documents List */}
      {activeTab === "documents" && (
        <div className="bg-white rounded-2xl border border-slate-200/80 p-8 shadow-xs space-y-4">
          <h3 className="font-bold text-slate-900 text-lg flex items-center gap-2 border-b border-slate-100 pb-4">
            <FileText className="w-5 h-5 text-indigo-600" />
            Case Documents & Files
          </h3>

          {!caseDetail?.documents || caseDetail.documents.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-sm">
              No documents found.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {caseDetail.documents.map((doc) => (
                <div key={doc.id} className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600 shrink-0">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-bold text-slate-900 text-sm truncate">{doc.name}</p>
                      <p className="text-xs text-slate-400 truncate">{doc.file_type}</p>
                    </div>
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shrink-0">
                    Processed
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Interactive Case QA Assistant */}
      {activeTab === "qa" && (
        <div className="bg-white rounded-2xl border border-slate-200/80 p-8 shadow-xs space-y-6">
          <div>
            <h3 className="font-bold text-slate-900 text-lg flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-indigo-600" />
              Interactive Case QA Assistant
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Ask specific legal questions regarding the parsed document chunks, FIR statements, or timeline events.
            </p>
          </div>

          {/* QA Chat Log */}
          <div className="min-h-[250px] max-h-[500px] overflow-y-auto space-y-4 p-4 bg-slate-50 rounded-2xl border border-slate-100">
            {qaHistory.length === 0 ? (
              <div className="text-center py-12 text-slate-400 text-sm">
                Ask a question below (e.g. &quot;What time did the incident occur according to the FIR?&quot;)
              </div>
            ) : (
              qaHistory.map((item, idx) => (
                <div key={idx} className="space-y-3">
                  {/* Question */}
                  <div className="flex justify-end">
                    <div className="bg-[#0B1437] text-white p-3.5 rounded-2xl rounded-tr-xs max-w-lg text-sm font-medium">
                      {item.question}
                    </div>
                  </div>

                  {/* Answer */}
                  <div className="flex justify-start">
                    <div className="bg-white border border-slate-200 p-4 rounded-2xl rounded-tl-xs max-w-2xl text-sm text-slate-800 space-y-3 shadow-2xs">
                      <p className="leading-relaxed whitespace-pre-wrap">{item.answer}</p>

                      {/* Citations */}
                      {item.citations && item.citations.length > 0 && (
                        <div className="pt-2 border-t border-slate-100 text-xs space-y-1">
                          <p className="font-bold text-slate-600">Citations & Source Chunks:</p>
                          {item.citations.map((c: any, cIdx: number) => (
                            <div key={cIdx} className="bg-slate-50 p-2 rounded-lg border border-slate-100 text-slate-600 font-mono text-[11px]">
                              {typeof c === "string" ? c : JSON.stringify(c)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}

            {asking && (
              <div className="flex justify-start">
                <div className="bg-white border border-slate-200 p-4 rounded-2xl text-sm text-slate-500 inline-flex items-center gap-2 shadow-2xs">
                  <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
                  Analyzing document chunks and generating answer...
                </div>
              </div>
            )}
          </div>

          {/* Ask Input Form */}
          <form onSubmit={handleSendQuestion} className="flex gap-3">
            <input
              type="text"
              required
              placeholder="Ask a question about this case..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="flex-1 px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
            <button
              type="submit"
              disabled={asking || !question.trim()}
              className="bg-[#0B1437] hover:bg-[#152458] text-white px-6 py-3 rounded-xl text-sm font-bold transition flex items-center gap-2 shadow-xs disabled:opacity-50"
            >
              {asking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Send
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
