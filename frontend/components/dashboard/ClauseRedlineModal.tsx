"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Loader2,
  Scale,
  RefreshCw,
  FileCheck,
  Eye,
  Code2,
} from "lucide-react";
import toast from "react-hot-toast";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { apiClient } from "@/services/api";

interface ClauseRedlineModalProps {
  contractId: string;
  clause: {
    id: string;
    section_title: string;
    clause_type: string;
    raw_text: string;
    severity: string;
    risk_description?: string;
    legal_reasoning?: string;
  };
  isOpen: boolean;
  onClose: () => void;
  onRevisionApplied?: (revisedText: string, originalText: string) => void;
}

export function ClauseRedlineModal({
  contractId,
  clause,
  isOpen,
  onClose,
  onRevisionApplied,
}: ClauseRedlineModalProps) {
  const [customPrompt, setCustomPrompt] = useState("");
  const [favorParty, setFavorParty] = useState("balanced");
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [activeTab, setActiveTab] = useState<"preview" | "raw">("preview");
  const [renderedHtml, setRenderedHtml] = useState<string>("");
  const [rationaleHtml, setRationaleHtml] = useState<string>("");
  const [notesHtml, setNotesHtml] = useState<string>("");
  const [revision, setRevision] = useState<{
    revised_text: string;
    rationale: string;
    remedied_risks: string[];
    statutory_compliance_notes: string;
  } | null>(null);

  useEffect(() => {
    if (!revision) {
      setRenderedHtml("");
      setRationaleHtml("");
      setNotesHtml("");
      return;
    }
    try {
      marked.setOptions({
        gfm: true,
        breaks: true,
      });

      const formatMd = (raw: string) => {
        if (!raw) return "";
        // Separate packed numbered list items (e.g. "...required**. 2. **Explicit...") into distinct list lines
        const normalized = raw.replace(/([.!?])\s+(\d+\.\s+\*\*)/g, "$1\n\n$2");
        const parsed = marked.parse(normalized);
        const htmlStr = typeof parsed === "string" ? parsed : "";
        return DOMPurify.sanitize(htmlStr);
      };

      setRenderedHtml(formatMd(revision.revised_text || ""));
      setRationaleHtml(formatMd(revision.rationale || ""));
      setNotesHtml(formatMd(revision.statutory_compliance_notes || ""));
    } catch {
      setRenderedHtml(`<p>${revision.revised_text || ""}</p>`);
      setRationaleHtml(`<p>${revision.rationale || ""}</p>`);
      setNotesHtml(`<p>${revision.statutory_compliance_notes || ""}</p>`);
    }
  }, [revision]);

  if (!isOpen) return null;

  const handleGenerateRedraft = async () => {
    if (!contractId || !clause?.raw_text) return;
    setLoading(true);

    try {
      const data = await apiClient.redraftClause(contractId, {
        clause_id: clause.id,
        clause_title: clause.section_title,
        original_text: clause.raw_text,
        custom_prompt: customPrompt.trim() || undefined,
        favor_party: favorParty,
      });

      setRevision({
        revised_text: data.revised_text,
        rationale: data.rationale,
        remedied_risks: data.remedied_risks || [],
        statutory_compliance_notes: data.statutory_compliance_notes || "",
      });
      toast.success("AI Clause Redraft generated!");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to generate redraft.");
    } finally {
      setLoading(false);
    }
  };

  const handleApplyRevision = async () => {
    if (!contractId || !clause?.id || !revision?.revised_text) return;
    setApplying(true);

    try {
      await apiClient.applyClauseRevision(contractId, {
        clause_id: clause.id,
        revised_text: revision.revised_text,
        rationale: revision.rationale,
      });

      toast.success("Clause updated in contract analysis!");
      if (onRevisionApplied) {
        onRevisionApplied(revision.revised_text, clause.raw_text);
      }
      onClose();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to apply revision.");
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white w-full max-w-4xl max-h-[92vh] rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600/10 text-blue-600 flex items-center justify-center">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                Edit & Redraft: {clause.section_title || `Clause ${clause.id}`}
                <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold border bg-slate-100 text-slate-700">
                  {clause.clause_type}
                </span>
              </h2>
              <p className="text-xs text-slate-500">
                Ground in Indian Contract Act 1872 with customized negotiation instructions
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded-lg transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-slate-800">
          {/* Risk Warning Context */}
          {clause.risk_description && (
            <div className="p-3.5 bg-amber-50/80 border border-amber-200 rounded-xl flex items-start gap-3 text-xs">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-amber-900">
                  Identified Vulnerability ({clause.severity}):{" "}
                </span>
                <span className="text-amber-800">{clause.risk_description}</span>
                {clause.legal_reasoning && (
                  <p className="text-amber-700 mt-1 italic">
                    Legal Note: {clause.legal_reasoning}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* User Prompt Controls */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                Custom Editing Instructions / Negotiation Stance
              </label>
              <div className="flex items-center gap-1 text-xs">
                <span className="text-slate-500 mr-1">Bias:</span>
                {["balanced", "client", "counterparty"].map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setFavorParty(mode)}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize transition ${
                      favorParty === mode
                        ? "bg-blue-600 text-white shadow-xs"
                        : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="E.g., 'Cap liability to 12 months fees and make indemnification mutual', 'Remove post-termination non-compete'..."
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleGenerateRedraft()}
                className="flex-1 px-3.5 py-2 text-sm bg-white border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 text-slate-800 placeholder-slate-400"
              />
              <button
                onClick={handleGenerateRedraft}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold flex items-center gap-2 transition shrink-0"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Drafting...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    Redraft Clause
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Side-by-Side Comparison: Original vs Revised */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Original */}
            <div className="border border-slate-200 rounded-xl overflow-hidden flex flex-col bg-slate-50/50">
              <div className="px-4 py-2.5 bg-slate-100 border-b border-slate-200 text-xs font-bold text-slate-700 flex items-center justify-between">
                <span>Original Clause</span>
                <span className="text-[10px] text-slate-400 uppercase font-mono">Current Text</span>
              </div>
              <div className="p-4 flex-1 text-xs text-slate-700 font-mono leading-relaxed whitespace-pre-wrap overflow-y-auto max-h-72">
                {clause.raw_text}
              </div>
            </div>

            {/* Revised */}
            <div className="border border-blue-200 rounded-xl overflow-hidden flex flex-col bg-blue-50/20">
              <div className="px-4 py-2 bg-blue-100/60 border-b border-blue-200 text-xs font-bold text-blue-900 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  Proposed Redraft
                </span>
                <div className="flex items-center gap-2">
                  {revision && (
                    <div className="inline-flex rounded-lg border border-blue-200 bg-white p-0.5 text-[10px]">
                      <button
                        type="button"
                        onClick={() => setActiveTab("preview")}
                        className={`px-2 py-0.5 rounded-md font-semibold flex items-center gap-1 transition ${
                          activeTab === "preview"
                            ? "bg-blue-600 text-white shadow-xs"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        <Eye className="w-3 h-3" />
                        Formatted
                      </button>
                      <button
                        type="button"
                        onClick={() => setActiveTab("raw")}
                        className={`px-2 py-0.5 rounded-md font-semibold flex items-center gap-1 transition ${
                          activeTab === "raw"
                            ? "bg-blue-600 text-white shadow-xs"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        <Code2 className="w-3 h-3" />
                        Raw MD
                      </button>
                    </div>
                  )}
                  <span className="text-[10px] text-blue-500 uppercase font-mono hidden sm:inline">
                    Indian Law Compliant
                  </span>
                </div>
              </div>
              <div className="p-4 flex-1 text-xs text-slate-800 leading-relaxed overflow-y-auto max-h-72">
                {revision ? (
                  activeTab === "preview" && renderedHtml ? (
                    <div
                      className="contract-markdown markdown-body max-w-none text-xs leading-relaxed text-slate-800 bg-transparent"
                      dangerouslySetInnerHTML={{ __html: renderedHtml }}
                    />
                  ) : (
                    <div className="font-mono text-xs whitespace-pre-wrap text-slate-800 leading-relaxed">
                      {revision.revised_text}
                    </div>
                  )
                ) : (
                  <span className="text-slate-400 italic font-sans text-xs">
                    Click &apos;Redraft Clause&apos; above to generate an AI-revised proposal that cures identified risks.
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Rationale & Remedied Risks */}
          {revision && (
            <div className="space-y-3 bg-emerald-50/50 border border-emerald-200 rounded-xl p-4 text-xs">
              <div>
                <h4 className="font-bold text-emerald-950 flex items-center gap-1.5 mb-2">
                  <Scale className="w-4 h-4 text-emerald-700" />
                  Legal Rationale & Statutory Compliance
                </h4>
                {rationaleHtml ? (
                  <div
                    className="contract-markdown markdown-body max-w-none text-xs leading-relaxed text-emerald-950 bg-transparent space-y-2 [&_p]:text-emerald-950 [&_li]:text-emerald-900 [&_strong]:text-emerald-950"
                    dangerouslySetInnerHTML={{ __html: rationaleHtml }}
                  />
                ) : (
                  <p className="text-emerald-900 mt-1 leading-relaxed whitespace-pre-wrap">
                    {revision.rationale}
                  </p>
                )}

                {revision.statutory_compliance_notes && (
                  <div className="mt-3 pt-2.5 border-t border-emerald-200/70">
                    <span className="font-semibold text-emerald-900 text-[11px] block mb-1">
                      Statutory Grounding:
                    </span>
                    {notesHtml ? (
                      <div
                        className="contract-markdown markdown-body max-w-none text-[11px] leading-relaxed text-emerald-900 bg-transparent [&_p]:text-emerald-900 [&_li]:text-emerald-800 [&_strong]:text-emerald-950"
                        dangerouslySetInnerHTML={{ __html: notesHtml }}
                      />
                    ) : (
                      <p className="text-emerald-800 font-mono text-[11px] whitespace-pre-wrap">
                        {revision.statutory_compliance_notes}
                      </p>
                    )}
                  </div>
                )}
              </div>

              {revision.remedied_risks && revision.remedied_risks.length > 0 && (
                <div>
                  <h5 className="font-semibold text-emerald-900 text-[11px] mb-1">
                    Vulnerabilities Remedied:
                  </h5>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {revision.remedied_risks.map((risk, i) => (
                      <li key={i} className="flex items-center gap-1.5 text-emerald-800 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        {risk}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 font-medium transition"
          >
            Cancel
          </button>

          <button
            onClick={handleApplyRevision}
            disabled={!revision || applying}
            className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white rounded-xl text-sm font-semibold flex items-center gap-2 shadow-xs transition"
          >
            {applying ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Applying...
              </>
            ) : (
              <>
                <FileCheck className="w-4 h-4" />
                Apply Revision to Contract
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
