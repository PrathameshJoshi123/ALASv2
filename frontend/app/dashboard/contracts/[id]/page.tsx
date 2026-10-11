"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  AlertCircle,
  CheckCircle,
  Info,
  Loader2,
  ArrowLeft,
  Clock3,
  FileText,
  Database,
  FileSearch,
  Bot,
  MessageSquare,
} from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { JuristChatDrawer } from "@/components/dashboard/JuristChatDrawer";

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

export default function ContractDetailsPage() {
  const params = useParams();
  const contractId = params.id as string;

  const [contract, setContract] = useState<any>(null);
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [expandedClauses, setExpandedClauses] = useState<Set<string>>(
    new Set(),
  );
  const [contractMarkdownPreview, setContractMarkdownPreview] = useState("");
  const [finalAnalysisPreview, setFinalAnalysisPreview] = useState("");
  const [pollingActive, setPollingActive] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);

  const [selectedObligationCategory, setSelectedObligationCategory] =
    useState<string>("ALL");
  const [selectedRiskCategory, setSelectedRiskCategory] =
    useState<string>("ALL");
  const [resolvedQuestions, setResolvedQuestions] = useState<Set<number>>(
    new Set(),
  );

  const toggleQuestionResolved = (index: number) => {
    setResolvedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  useEffect(() => {
    const fetchContractData = async (isInitial = false) => {
      try {
        if (isInitial) {
          setLoading(true);
        }

        const [contractRes, analysisRes] = await Promise.all([
          apiClient.getContractDetails(contractId),
          apiClient.getContractAnalysis(contractId),
        ]);

        setContract(contractRes);
        setClauses(analysisRes.clauses || []);
        setAnalysis(analysisRes);

        if (analysisRes?.analysis_markdown || analysisRes?.analysis_summary) {
          setFinalAnalysisPreview(
            String(
              analysisRes.analysis_markdown || analysisRes.analysis_summary || "",
            ).slice(0, 1200),
          );
        }

        if (contractRes?.name || contractRes?.contract_type) {
          const previewText = contractRes.analysis_summary
            ? `Document: ${contractRes.name}\nType: ${contractRes.contract_type}\nStatus: ${contractRes.status}\n\nSummary:\n${contractRes.analysis_summary}`
            : `Document: ${contractRes.name}\nType: ${contractRes.contract_type}\nStatus: ${contractRes.status}`;
          setContractMarkdownPreview(previewText.slice(0, 900));
        }

        setPollingActive(false);
      } catch (error) {
        if (isInitial) {
          toast.error("Failed to load contract details");
        }
      } finally {
        if (isInitial) {
          setLoading(false);
        }
      }
    };

    if (contractId) {
      fetchContractData(true);
    }
  }, [contractId]);

  const toggleClauseExpand = (clauseId: string) => {
    setExpandedClauses((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(clauseId)) {
        newSet.delete(clauseId);
      } else {
        newSet.add(clauseId);
      }
      return newSet;
    });
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return <AlertCircle className="w-5 h-5 text-red-600" />;
      case "HIGH":
        return <AlertCircle className="w-5 h-5 text-orange-600" />;
      case "MEDIUM":
        return <Info className="w-5 h-5 text-yellow-600" />;
      default:
        return <CheckCircle className="w-5 h-5 text-green-600" />;
    }
  };

  const getSeverityBadgeColor = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return "bg-red-100 text-red-800 border-red-300";
      case "HIGH":
        return "bg-orange-100 text-orange-800 border-orange-300";
      case "MEDIUM":
        return "bg-yellow-100 text-yellow-800 border-yellow-300";
      default:
        return "bg-green-100 text-green-800 border-green-300";
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-600">Loading contract analysis...</p>
        </div>
      </div>
    );
  }

  if (!contract) {
    return (
      <div className="p-8">
        <p className="text-center text-slate-600">Contract not found</p>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Link
            href="/dashboard/contracts"
            className="text-blue-600 hover:text-blue-700"
          >
            <ArrowLeft className="w-6 h-6" />
          </Link>
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              {contract.original_filename || contract.markdown_file}
            </h1>
            <p className="text-slate-600 mt-1">
              Counterparty: {contract.counterparty_name || contract.company_name}
            </p>
            <div className="mt-2 flex items-center gap-2 text-xs">
              {pollingActive ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 text-blue-600 animate-spin" />
                  <span className="text-blue-700 font-medium">
                    Live polling active: waiting for worker updates...
                  </span>
                </>
              ) : (
                <>
                  <CheckCircle className="w-3.5 h-3.5 text-green-600" />
                  <span className="text-green-700 font-medium">
                    Analysis pipeline completed
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setIsChatOpen(true)}
            className="flex items-center gap-2 bg-[#0B1437] hover:bg-[#152458] text-white px-5 py-2.5 rounded-xl font-bold text-sm shadow-md transition-all cursor-pointer"
          >
            <Bot className="w-5 h-5 text-blue-400" />
            <span>Ask AI Jurist</span>
          </button>

          <Link
            href={`/dashboard/tenant-files?id=${contractId}`}
            className="flex items-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-4 py-2.5 rounded-xl font-semibold text-sm shadow-sm transition-all"
          >
            <FileText className="w-4 h-4 text-slate-500" />
            <span>Open Editor</span>
          </Link>
        </div>
      </div>

      {/* Live worker progress */}
      <div className="bg-white rounded-lg shadow border border-slate-200 p-6">
        <h2 className="text-lg font-bold text-slate-900 mb-4">
          Live Worker Progress
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div
            className={`rounded-lg border p-3 ${contract?.live?.markdown_ready ? "border-green-200 bg-green-50" : "border-slate-200 bg-slate-50"}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <FileText className="w-4 h-4 text-slate-700" />
              <span className="text-xs font-semibold text-slate-700">
                Markdown Parsed
              </span>
            </div>
            <p className="text-xs text-slate-600">
              {contract?.live?.markdown_ready ? "Ready" : "Pending"}
            </p>
          </div>

          <div
            className={`rounded-lg border p-3 ${contract?.live?.result_ready ? "border-green-200 bg-green-50" : "border-slate-200 bg-slate-50"}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <FileSearch className="w-4 h-4 text-slate-700" />
              <span className="text-xs font-semibold text-slate-700">
                Analysis Result JSON
              </span>
            </div>
            <p className="text-xs text-slate-600">
              {contract?.live?.result_ready ? "Ready" : "Pending"}
            </p>
          </div>

          <div
            className={`rounded-lg border p-3 ${contract?.live?.final_analysis_ready ? "border-green-200 bg-green-50" : "border-slate-200 bg-slate-50"}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Clock3 className="w-4 h-4 text-slate-700" />
              <span className="text-xs font-semibold text-slate-700">
                Final Analysis Markdown
              </span>
            </div>
            <p className="text-xs text-slate-600">
              {contract?.live?.final_analysis_ready ? "Ready" : "Pending"}
            </p>
          </div>

          <div
            className={`rounded-lg border p-3 ${contract?.live?.vector_store_ready ? "border-green-200 bg-green-50" : "border-slate-200 bg-slate-50"}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Database className="w-4 h-4 text-slate-700" />
              <span className="text-xs font-semibold text-slate-700">
                Vector Store
              </span>
            </div>
            <p className="text-xs text-slate-600">
              {contract?.live?.vector_store_ready ? "Ready" : "Pending"}
            </p>
          </div>
        </div>
      </div>

      {/* Live markdown previews */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">
            Contract Markdown Preview
          </h3>
          <pre className="whitespace-pre-wrap text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded p-3 max-h-64 overflow-y-auto">
            {contractMarkdownPreview || "Waiting for markdown content..."}
          </pre>
        </div>

        <div className="bg-white rounded-lg shadow border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">
            Final Analysis Preview
          </h3>
          <pre className="whitespace-pre-wrap text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded p-3 max-h-64 overflow-y-auto">
            {finalAnalysisPreview || "Waiting for final analysis markdown..."}
          </pre>
        </div>
      </div>

      {/* Risk Score Card */}
      <div className="bg-white rounded-lg shadow border border-slate-200 p-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Overall Risk */}
          <div className="text-center">
            <p className="text-slate-600 text-sm font-medium mb-3">
              Overall Risk Score
            </p>
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-blue-100 to-blue-50 flex items-center justify-center mx-auto mb-3">
              <span
                className={`text-4xl font-bold ${
                  (analysis?.overall_risk_score || 0) >= 70
                    ? "text-red-600"
                    : (analysis?.overall_risk_score || 0) >= 40
                      ? "text-orange-600"
                      : "text-green-600"
                }`}
              >
                {analysis?.overall_risk_score || 0}%
              </span>
            </div>
            <p className="text-sm text-slate-600">Out of 100</p>
          </div>

          {/* Issues Summary */}
          <div>
            <p className="text-slate-600 text-sm font-medium mb-4">
              Issues Found
            </p>
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-600" />
                <span className="text-slate-700">
                  {analysis?.critical_issues || 0} Critical Issues
                </span>
              </div>
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-orange-600" />
                <span className="text-slate-700">
                  {analysis?.high_issues || 0} High Priority Issues
                </span>
              </div>
              <div className="flex items-center gap-3">
                <Info className="w-5 h-5 text-yellow-600" />
                <span className="text-slate-700">
                  {analysis?.medium_issues || 0} Medium Priority Issues
                </span>
              </div>
            </div>
          </div>

          {/* Contract Details */}
          <div>
            <p className="text-slate-600 text-sm font-medium mb-4">
              Contract Details
            </p>
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-slate-500">Type</p>
                <p className="text-slate-900 font-medium">
                  {contract.contract_type}
                </p>
              </div>
              <div>
                <p className="text-slate-500">Status</p>
                <p className="text-slate-900 font-medium">{contract.status}</p>
              </div>
              <div>
                <p className="text-slate-500">Uploaded</p>
                <p className="text-slate-900 font-medium">
                  {new Date(contract.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Key Findings Section */}
      <div className="bg-white rounded-lg shadow border border-slate-200 overflow-hidden">
        <div className="px-8 py-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FileSearch className="w-5 h-5 text-blue-600" />
            <h2 className="text-xl font-bold text-slate-900">
              Key Contract Findings
            </h2>
          </div>
          <span className="px-3 py-1 bg-blue-100 text-blue-800 text-xs font-semibold rounded-full">
            {(analysis?.key_findings || []).length} Findings
          </span>
        </div>
        <div className="p-8">
          {(analysis?.key_findings || []).length === 0 ? (
            <p className="text-slate-500 text-sm italic">
              No key findings available yet for this contract.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {(analysis?.key_findings || []).map(
                (finding: string, idx: number) => (
                  <div
                    key={idx}
                    className="flex items-start gap-3 p-4 bg-slate-50 rounded-lg border border-slate-200"
                  >
                    <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                    <p className="text-sm text-slate-800 leading-relaxed font-medium">
                      {finding}
                    </p>
                  </div>
                ),
              )}
            </div>
          )}
        </div>
      </div>

      {/* Categorized Obligations Section */}
      <div className="bg-white rounded-lg shadow border border-slate-200 overflow-hidden">
        <div className="px-8 py-5 border-b border-slate-200 bg-slate-50 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-indigo-600" />
            <div>
              <h2 className="text-xl font-bold text-slate-900">
                Categorized Obligations
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                {(analysis?.obligations || []).length} total obligations identified
              </p>
            </div>
          </div>

          {/* Category Tabs */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedObligationCategory("ALL")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                selectedObligationCategory === "ALL"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
              }`}
            >
              All ({(analysis?.obligations || []).length})
            </button>
            {Array.from(
              new Set(
                (analysis?.obligations || []).map(
                  (ob: any) =>
                    ob.category || ob.details?.category || "General",
                ),
              ),
            ).map((cat: any) => (
              <button
                key={cat}
                onClick={() => setSelectedObligationCategory(String(cat))}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  selectedObligationCategory === String(cat)
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        <div className="p-8 space-y-4">
          {(analysis?.obligations || []).length === 0 ? (
            <p className="text-slate-500 text-sm italic">
              No obligations extracted yet.
            </p>
          ) : (
            (analysis?.obligations || [])
              .filter((ob: any) => {
                if (selectedObligationCategory === "ALL") return true;
                const cat = ob.category || ob.details?.category || "General";
                return (
                  String(cat).toLowerCase() ===
                  selectedObligationCategory.toLowerCase()
                );
              })
              .map((ob: any, idx: number) => {
                const text =
                  typeof ob === "string"
                    ? ob
                    : ob.description || ob.details?.description || JSON.stringify(ob);
                const category =
                  typeof ob === "object"
                    ? ob.category || ob.details?.category || "General"
                    : "General";
                const actor = ob.details?.actor;

                return (
                  <div
                    key={ob.id || idx}
                    className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-4"
                  >
                    <div className="space-y-1 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                          {category}
                        </span>
                        {actor && (
                          <span className="px-2 py-0.5 rounded text-xs bg-slate-200 text-slate-700 font-medium">
                            Party: {actor}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-800 font-medium">
                        {text}
                      </p>
                    </div>
                  </div>
                );
              })
          )}
        </div>
      </div>

      {/* Categorized Risks Section */}
      <div className="bg-white rounded-lg shadow border border-slate-200 overflow-hidden">
        <div className="px-8 py-5 border-b border-slate-200 bg-slate-50 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600" />
            <div>
              <h2 className="text-xl font-bold text-slate-900">
                Categorized Contract Risks
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                {(analysis?.risks || []).length} total potential risk factors
              </p>
            </div>
          </div>

          {/* Risk Category Tabs */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedRiskCategory("ALL")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                selectedRiskCategory === "ALL"
                  ? "bg-amber-600 text-white shadow-sm"
                  : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
              }`}
            >
              All ({(analysis?.risks || []).length})
            </button>
            {Array.from(
              new Set(
                (analysis?.risks || []).map(
                  (r: any) => r.category || r.details?.category || "General",
                ),
              ),
            ).map((cat: any) => (
              <button
                key={cat}
                onClick={() => setSelectedRiskCategory(String(cat))}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  selectedRiskCategory === String(cat)
                    ? "bg-amber-600 text-white shadow-sm"
                    : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        <div className="p-8 space-y-4">
          {(analysis?.risks || []).length === 0 ? (
            <p className="text-slate-500 text-sm italic">
              No risks categorized yet.
            </p>
          ) : (
            (analysis?.risks || [])
              .filter((r: any) => {
                if (selectedRiskCategory === "ALL") return true;
                const cat = r.category || r.details?.category || "General";
                return (
                  String(cat).toLowerCase() ===
                  selectedRiskCategory.toLowerCase()
                );
              })
              .map((r: any, idx: number) => {
                const text =
                  typeof r === "string"
                    ? r
                    : r.description || r.details?.description || JSON.stringify(r);
                const category =
                  typeof r === "object"
                    ? r.category || r.details?.category || "General"
                    : "General";
                const severity = String(
                  r.severity || r.details?.severity || "MEDIUM",
                ).toUpperCase();

                return (
                  <div
                    key={r.id || idx}
                    className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-2"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2.5 py-0.5 rounded text-xs font-bold border ${getSeverityBadgeColor(
                          severity,
                        )}`}
                      >
                        {severity}
                      </span>
                      <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                        {category}
                      </span>
                    </div>
                    <p className="text-sm text-slate-800 font-medium">{text}</p>
                    {r.details?.mitigation && (
                      <p className="text-xs text-emerald-700 bg-emerald-50 p-2.5 rounded border border-emerald-200">
                        <strong className="font-semibold">Mitigation:</strong>{" "}
                        {r.details.mitigation}
                      </p>
                    )}
                  </div>
                );
              })
          )}
        </div>
      </div>

      {/* Unresolved Questions / Contract Improvement Opportunities */}
      <div className="bg-white rounded-lg shadow border border-slate-200 overflow-hidden">
        <div className="px-8 py-5 border-b border-slate-200 bg-amber-50/50 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Info className="w-5 h-5 text-amber-600" />
            <div>
              <h2 className="text-xl font-bold text-slate-900">
                Unresolved Questions & Improvement Opportunities
              </h2>
              <p className="text-xs text-slate-600 mt-0.5">
                Clarify these questions to improve and strengthen the contract before signing
              </p>
            </div>
          </div>
          <span className="px-3 py-1 bg-amber-100 text-amber-800 text-xs font-semibold rounded-full">
            {(analysis?.unresolved_questions || []).length} Open Questions
          </span>
        </div>

        <div className="p-8">
          {(analysis?.unresolved_questions || []).length === 0 ? (
            <p className="text-slate-500 text-sm italic">
              No unresolved questions recorded for this contract.
            </p>
          ) : (
            <div className="space-y-3">
              {(analysis?.unresolved_questions || []).map(
                (question: string, idx: number) => {
                  const isResolved = resolvedQuestions.has(idx);
                  return (
                    <div
                      key={idx}
                      onClick={() => toggleQuestionResolved(idx)}
                      className={`p-4 rounded-lg border transition cursor-pointer flex items-start gap-3.5 ${
                        isResolved
                          ? "bg-slate-50 border-slate-200 opacity-60 line-through"
                          : "bg-white border-amber-200 hover:border-amber-400 shadow-sm"
                      }`}
                    >
                      <button className="mt-0.5 shrink-0 text-slate-400 hover:text-amber-600">
                        {isResolved ? (
                          <CheckCircle className="w-5 h-5 text-emerald-600" />
                        ) : (
                          <Info className="w-5 h-5 text-amber-600" />
                        )}
                      </button>
                      <div className="flex-1 space-y-1">
                        <p className="text-sm font-medium text-slate-800 leading-relaxed">
                          {question}
                        </p>
                        <p className="text-xs text-amber-700">
                          {isResolved
                            ? "Marked as clarified/reviewed"
                            : "Action item: Resolve with counterparty or legal counsel before signing"}
                        </p>
                      </div>
                    </div>
                  );
                },
              )}
            </div>
          )}
        </div>
      </div>

      {/* Clauses Analysis */}
      <div className="bg-white rounded-lg shadow border border-slate-200 overflow-hidden">
        <div className="px-8 py-6 border-b border-slate-200">
          <h2 className="text-xl font-bold text-slate-900">
            Clause-by-Clause Analysis
          </h2>
          <p className="text-slate-600 text-sm mt-1">
            {clauses.length} clauses identified
          </p>
        </div>

        <div className="divide-y divide-slate-200">
          {clauses.length === 0 ? (
            <p className="p-8 text-center text-slate-600">
              No clauses analysis available yet
            </p>
          ) : (
            clauses.map((clause) => (
              <div
                key={clause.id}
                className="border-b border-slate-100 last:border-b-0"
              >
                <button
                  onClick={() => toggleClauseExpand(clause.id)}
                  className="w-full px-8 py-4 hover:bg-slate-50 transition text-left flex items-start justify-between gap-4"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      {getSeverityIcon(clause.severity)}
                      <span className="font-medium text-slate-900">
                        {clause.section_title}
                      </span>
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold border ${getSeverityBadgeColor(clause.severity)}`}
                      >
                        {clause.severity}
                      </span>
                    </div>
                    <p className="text-sm text-slate-600">
                      Type: {clause.clause_type}
                    </p>
                  </div>
                  
                </button>

                {/* Expanded Content */}
                {expandedClauses.has(clause.id) && (
                  <div className="px-8 py-6 bg-slate-50 border-t border-slate-200 space-y-4">
                    {/* Clause Text */}
                    <div>
                      <h4 className="font-semibold text-slate-900 mb-2">
                        Clause Text
                      </h4>
                      <p className="text-slate-700 text-sm bg-white p-4 rounded border border-slate-200 italic">
                        "{clause.raw_text.substring(0, 300)}..."
                      </p>
                    </div>

                    {/* Risk Description */}
                    <div>
                      <h4 className="font-semibold text-slate-900 mb-2">
                        Risk Analysis
                      </h4>
                      <p className="text-slate-700 text-sm">
                        {clause.risk_description}
                      </p>
                    </div>

                    {/* Legal Reasoning */}
                    <div>
                      <h4 className="font-semibold text-slate-900 mb-2">
                        Legal Reasoning
                      </h4>
                      <p className="text-slate-700 text-sm bg-blue-50 p-4 rounded border border-blue-200">
                        {clause.legal_reasoning}
                      </p>
                    </div>

                    {/* Action Items */}
                    <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
                      <h4 className="font-semibold text-slate-900 mb-2">
                        Recommended Action
                      </h4>
                      <ul className="text-sm text-slate-700 space-y-1">
                        <li>• Review this clause with your legal team</li>
                        <li>
                          • Consider negotiating modifications if high risk
                        </li>
                        <li>• Document any approved exceptions</li>
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Summary */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="font-semibold text-blue-900 mb-3">Next Steps</h3>
        <ul className="text-sm text-blue-800 space-y-2">
          <li>✓ Review the risk assessment above</li>
          <li>✓ Discuss critical issues with your legal team</li>
          <li>✓ Propose alternative language if needed</li>
          <li>✓ Approve or reject the contract</li>
        </ul>
      </div>

      {/* Jurist AI In-Place Chat Drawer */}
      <JuristChatDrawer
        contractId={contractId}
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
      />
    </div>
  );
}
