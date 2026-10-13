"use client";

import React, { useState } from "react";
import {
  X,
  Sparkles,
  ArrowRight,
  Loader2,
  Scale,
  CheckCircle2,
  FileCheck,
  ShieldAlert,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";

interface AISelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedText: string;
  contractId: string;
  onApply: (replacementText: string) => void;
}

const PRESET_PROMPTS = [
  "Make mutual and commercially balanced",
  "Cap liability to fees paid in last 12 months",
  "Add 30-day notice and cure period before termination",
  "Comply with Section 27 Indian Contract Act (non-compete restraint)",
  "Limit indemnity to direct damages resulting from gross negligence",
  "Liquidated damages as genuine pre-estimate under Section 74 ICA",
];

export function AISelectionModal({
  isOpen,
  onClose,
  selectedText,
  contractId,
  onApply,
}: AISelectionModalProps) {
  const [customPrompt, setCustomPrompt] = useState("");
  const [favorParty, setFavorParty] = useState("balanced");
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState<{
    revised_text: string;
    rationale: string;
    remedied_risks: string[];
    statutory_compliance_notes: string;
  } | null>(null);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    if (!contractId || !selectedText.trim()) return;
    setLoading(true);

    try {
      const data = await apiClient.redraftClause(contractId, {
        clause_id: "selection",
        clause_title: "Selected Contract Provision",
        original_text: selectedText.trim(),
        custom_prompt: customPrompt.trim() || undefined,
        favor_party: favorParty,
      });

      setRevision({
        revised_text: data.revised_text,
        rationale: data.rationale,
        remedied_risks: data.remedied_risks || [],
        statutory_compliance_notes: data.statutory_compliance_notes || "",
      });
      toast.success("AI Redraft generated!");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to generate AI redraft.");
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    if (!revision?.revised_text) return;
    onApply(revision.revised_text);
    toast.success("Selection replaced with AI redraft!");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white w-full max-w-3xl max-h-[90vh] rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600/10 text-blue-600 flex items-center justify-center">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                Edit Selection with AI
                <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold border bg-blue-50 text-blue-700 border-blue-200">
                  Interactive Redrafter
                </span>
              </h2>
              <p className="text-xs text-slate-500">
                Redraft highlighted text using Indian legal grounding and custom instructions
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

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 custom-scrollbar text-slate-800">
          {/* Selected Text Preview */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Selected Text
            </label>
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl max-h-36 overflow-y-auto font-mono text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">
              {selectedText}
            </div>
          </div>

          {/* Quick Presets */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Quick Suggestions & Legal Presets
            </label>
            <div className="flex flex-wrap gap-2">
              {PRESET_PROMPTS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setCustomPrompt(preset)}
                  className={`text-xs px-3 py-1.5 rounded-lg border text-left transition ${
                    customPrompt === preset
                      ? "bg-blue-50 border-blue-400 text-blue-700 font-medium"
                      : "bg-white border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                  }`}
                >
                  + {preset}
                </button>
              ))}
            </div>
          </div>

          {/* Stance and Prompt */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-1 space-y-2">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                <Scale className="w-3.5 h-3.5 text-slate-400" /> Commercial Stance
              </label>
              <select
                value={favorParty}
                onChange={(e) => setFavorParty(e.target.value)}
                className="w-full text-xs font-medium border border-slate-300 rounded-xl px-3 py-2.5 bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="balanced">Balanced / Neutral</option>
                <option value="our_favor">In Our Favor</option>
                <option value="counterparty">In Counterparty Favor</option>
              </select>
            </div>

            <div className="md:col-span-2 space-y-2">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Custom Redrafting Prompt
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g., Make liability mutual, cap damages to 6 months fees..."
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleGenerate();
                    }
                  }}
                  className="flex-1 text-xs border border-slate-300 rounded-xl px-3 py-2 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={loading || !selectedText.trim()}
                  className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl font-bold text-xs shadow-sm transition whitespace-nowrap cursor-pointer"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> Drafting...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" /> Redraft
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Generated Result */}
          {revision && (
            <div className="space-y-4 pt-4 border-t border-slate-200 animate-in fade-in duration-300">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  Proposed AI Redraft
                </span>
                {revision.statutory_compliance_notes && (
                  <span className="text-[11px] font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-2.5 py-0.5 rounded-full">
                    {revision.statutory_compliance_notes}
                  </span>
                )}
              </div>

              <div className="p-4 bg-emerald-50/50 border border-emerald-200 rounded-xl font-mono text-xs text-slate-800 whitespace-pre-wrap leading-relaxed shadow-inner">
                {revision.revised_text}
              </div>

              {revision.rationale && (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600 space-y-1">
                  <span className="font-bold text-slate-800">Legal Rationale: </span>
                  <span>{revision.rationale}</span>
                </div>
              )}

              {revision.remedied_risks && revision.remedied_risks.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {revision.remedied_risks.map((risk, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 bg-amber-50 text-amber-800 border border-amber-200 rounded-md font-medium"
                    >
                      <ShieldAlert className="w-3 h-3 text-amber-600" />
                      {risk}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 flex items-center justify-end gap-3 bg-slate-50 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 hover:bg-slate-200/50 rounded-xl transition"
          >
            Cancel
          </button>
          {revision && (
            <button
              type="button"
              onClick={handleApply}
              className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold text-xs shadow-md transition cursor-pointer"
            >
              <FileCheck className="w-4 h-4" />
              Replace Selection in Document
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
