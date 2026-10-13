"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Undo2,
  Redo2,
  Save,
  Info,
  CheckCircle2,
  AlertTriangle,
  Globe,
  Loader2,
  Sparkles,
  Bot,
  Send,
  X,
  FileText,
  Download,
  Wand2,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { useSearchParams } from "next/navigation";
import { marked } from "marked";
import DOMPurify from "dompurify";
import React from "react";
import { ClauseRedlineModal } from "@/components/dashboard/ClauseRedlineModal";
import { AISelectionModal } from "@/components/dashboard/AISelectionModal";

const DocumentEditor = React.memo(
  function DocumentEditor({
    contract,
    htmlContent,
    onInput,
    onMouseUp,
  }: {
    contract: any;
    htmlContent: string;
    onInput: () => void;
    onMouseUp: () => void;
  }) {
    return (
      <div
        id="contract-document-content"
        contentEditable
        suppressContentEditableWarning
        onInput={onInput}
        onMouseUp={onMouseUp}
        onKeyUp={onMouseUp}
        className="outline-none focus:bg-slate-50/50 p-4 -mx-4 rounded-2xl transition-colors selection:bg-blue-100 selection:text-blue-900"
      >
        <h1 className="text-[32px] font-bold text-[#0B1437] mb-6 tracking-tight">
          {(
            contract?.original_filename ||
            contract?.markdown_file ||
            "MASTER_SERVICE_AGREEMENT"
          )
            ?.split(".")[0]
            ?.replaceAll("_", " ")}
        </h1>

        <div className="contract-markdown markdown-body max-w-none">
          <div dangerouslySetInnerHTML={{ __html: htmlContent }} />
        </div>
      </div>
    );
  },
  (prev, next) => {
    return (
      prev.htmlContent === next.htmlContent &&
      prev.contract?.original_filename === next.contract?.original_filename &&
      prev.contract?.markdown_file === next.contract?.markdown_file
    );
  },
);

DocumentEditor.displayName = "DocumentEditor";

export default function TenantFilesPage() {
  const searchParams = useSearchParams();
  const contractId = searchParams.get("id");

  const [isGenerating, setIsGenerating] = useState(() => {
    return searchParams.get("generating") === "true";
  });
  const [loadingStep, setLoadingStep] = useState(0);

  const [contract, setContract] = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [htmlContent, setHtmlContent] = useState<string>("");
  const [fetching, setFetching] = useState(!!contractId);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Right sidebar tab: "analysis" (Risk & Edit Suggestions) or "chat" (Ask AI Jurist)
  const [rightPanelTab, setRightPanelTab] = useState<"analysis" | "chat">("analysis");

  // Selection AI Editing state
  const [floatingPill, setFloatingPill] = useState<{
    text: string;
    x: number;
    y: number;
    range: Range;
  } | null>(null);
  const [isSelectionModalOpen, setIsSelectionModalOpen] = useState(false);
  const [selectedSnippet, setSelectedSnippet] = useState("");
  const [savedRange, setSavedRange] = useState<Range | null>(null);

  // Clause Redline state for suggestions
  const [activeClauseForRedraft, setActiveClauseForRedraft] = useState<any | null>(null);

  // Chat Q&A state
  const [qaInput, setQaInput] = useState("");
  const [qaLoading, setQaLoading] = useState(false);
  const [qaHistory, setQaHistory] = useState<
    Array<{
      id: string;
      question: string;
      answer: string;
      answerHtml: string;
      isPending: boolean;
      isError: boolean;
    }>
  >([]);
  const [pollingActive, setPollingActive] = useState(false);
  const [expandedClauses, setExpandedClauses] = useState<Set<number>>(
    new Set(),
  );
  const qaThreadRef = useRef<HTMLDivElement | null>(null);
  const qaInputRef = useRef<HTMLTextAreaElement | null>(null);

  const renderMarkdownToHtml = useCallback(async (content: string) => {
    try {
      marked.setOptions({
        gfm: true,
        breaks: true,
      });

      const rendered = marked.parse(content);
      const renderedHtml =
        typeof rendered === "string" ? rendered : await rendered;
      return DOMPurify.sanitize(renderedHtml);
    } catch (err) {
      const escaped = DOMPurify.sanitize(content, { ALLOWED_TAGS: [] });
      return `<p>${escaped}</p>`;
    }
  }, []);

  useEffect(() => {
    async function parseMarkdown() {
      const content =
        analysis?.analysis_markdown ||
        contract?.analysis_markdown ||
        contract?.analysis?.analysis_markdown ||
        "Analysis markdown will appear here once processing is complete.";
      const sanitized = await renderMarkdownToHtml(content);
      setHtmlContent(sanitized);
    }
    parseMarkdown();
  }, [analysis?.analysis_markdown, contract?.analysis_markdown, contract?.analysis?.analysis_markdown, renderMarkdownToHtml]);

  const fetchContractData = useCallback(
    async (isPolling = false) => {
      if (!contractId) return;
      try {
        if (!isPolling) setFetching(true);
        const [contractData, analysisData] = await Promise.all([
          apiClient.getContractDetails(contractId),
          apiClient.getContractAnalysis(contractId),
        ]);
        setContract(contractData);
        setAnalysis(analysisData);
        setPollingActive(false);
      } catch (error) {
        console.error("Failed to fetch contract data", error);
      } finally {
        setFetching(false);
      }
    },
    [contractId],
  );

  useEffect(() => {
    if (!isGenerating && contractId) {
      fetchContractData(false);
    }
  }, [contractId, isGenerating, fetchContractData]);

  const taskId = searchParams.get("task_id");

  useEffect(() => {
    if (!isGenerating) return;

    const stepInterval = setInterval(() => {
      setLoadingStep((s) => s + 1);
    }, 1800);

    let pollInterval: NodeJS.Timeout | null = null;

    if (contractId && taskId) {
      pollInterval = setInterval(async () => {
        try {
          const statusRes = await apiClient.getProcessingStatus(contractId, taskId);
          const taskStatus = statusRes?.status || statusRes?.state;

          if (taskStatus === "SUCCESS" || statusRes?.successful) {
            if (pollInterval) clearInterval(pollInterval);
            clearInterval(stepInterval);

            await fetchContractData(false);
            setIsGenerating(false);
            toast.success("Contract drafted successfully by AI Agent!");

            const url = new URL(window.location.href);
            url.searchParams.delete("generating");
            url.searchParams.delete("drafting");
            url.searchParams.set("generated", "true");
            window.history.replaceState(null, "", url.pathname + url.search);
          } else if (taskStatus === "FAILURE") {
            if (pollInterval) clearInterval(pollInterval);
            clearInterval(stepInterval);
            setIsGenerating(false);
            toast.error("Contract drafting task failed.");
          }
        } catch (e) {
          console.error("Task polling error", e);
        }
      }, 2500);
    } else {
      const timeout = setTimeout(async () => {
        clearInterval(stepInterval);
        if (contractId) {
          await fetchContractData(false);
        }
        setIsGenerating(false);
        const url = new URL(window.location.href);
        url.searchParams.delete("generating");
        url.searchParams.set("generated", "true");
        window.history.replaceState(null, "", url.pathname + url.search);
      }, 5500);

      return () => {
        clearInterval(stepInterval);
        clearTimeout(timeout);
      };
    }

    return () => {
      clearInterval(stepInterval);
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [isGenerating, contractId, taskId, fetchContractData]);

  const handleContentChange = useCallback(() => {
    setHasUnsavedChanges((prev) => {
      if (!prev) return true;
      return prev;
    });
  }, []);

  // Track text selection for floating AI edit pill
  const handleEditorMouseUp = useCallback(() => {
    setTimeout(() => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) {
        setFloatingPill(null);
        return;
      }

      const text = selection.toString().trim();
      if (text.length < 3) {
        setFloatingPill(null);
        return;
      }

      const editor = document.getElementById("contract-document-content");
      if (!editor || !selection.anchorNode || !editor.contains(selection.anchorNode)) {
        setFloatingPill(null);
        return;
      }

      try {
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        setFloatingPill({
          text,
          x: Math.max(20, rect.left + rect.width / 2),
          y: Math.max(20, rect.top - 12),
          range: range.cloneRange(),
        });
      } catch (e) {
        setFloatingPill(null);
      }
    }, 50);
  }, []);

  const handleOpenSelectionEditor = () => {
    if (!floatingPill) return;
    setSelectedSnippet(floatingPill.text);
    setSavedRange(floatingPill.range);
    setIsSelectionModalOpen(true);
    setFloatingPill(null);
  };

  const handleApplySelectionReplacement = (replacementText: string) => {
    const editor = document.getElementById("contract-document-content");
    if (savedRange && editor) {
      try {
        const selection = window.getSelection();
        if (selection) {
          selection.removeAllRanges();
          selection.addRange(savedRange);
          document.execCommand("insertText", false, replacementText);
        }
      } catch (err) {
        if (selectedSnippet) {
          editor.innerHTML = editor.innerHTML.replace(selectedSnippet, replacementText);
        }
      }
    } else if (selectedSnippet && editor) {
      editor.innerHTML = editor.innerHTML.replace(selectedSnippet, replacementText);
    }
    setHasUnsavedChanges(true);
  };

  const getEditorContent = () => {
    const editor = document.getElementById("contract-document-content");
    if (!editor) return "";
    return editor.innerText || editor.textContent || "";
  };

  const handleSaveDraft = async () => {
    if (!contractId) return;
    const content = getEditorContent();
    setIsSaving(true);
    const saveToast = toast.loading("Saving contract draft...");

    try {
      await apiClient.saveContractContent(contractId, content);
      setHasUnsavedChanges(false);
      toast.success("Draft saved successfully!", { id: saveToast });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to save draft.", { id: saveToast });
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAndAnalyze = async () => {
    if (!contractId) return;
    const content = getEditorContent();
    setIsAnalyzing(true);
    const analysisToast = toast.loading("Saving and analyzing contract...");

    try {
      if (content) {
        await apiClient.saveContractContent(contractId, content);
      }
      await apiClient.analyzeContract(contractId);
      const result = await apiClient.getContractAnalysis(contractId);
      setAnalysis(result);
      setHasUnsavedChanges(false);
      toast.success("Analysis complete. Risk profile updated!", {
        id: analysisToast,
      });
    } catch (error: any) {
      console.error("Analysis failed", error);
      toast.error(error?.response?.data?.detail || "Failed to re-analyze contract.", { id: analysisToast });
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Open Clause Redline from right sidebar suggestion
  const handleOpenClauseRedraft = (clause: any, index: number) => {
    setActiveClauseForRedraft({
      id: String(clause.id || clause.clause_number || index + 1),
      section_title: clause.section_title || clause.title || `Clause ${index + 1}`,
      clause_type: clause.clause_type || "General Provision",
      raw_text: clause.raw_text || "",
      severity: clause.severity || "MEDIUM",
      risk_description: clause.risk_description || "",
      legal_reasoning: clause.legal_reasoning || "",
    });
  };

  const handleClauseRevisionApplied = (revisedText: string, originalText: string) => {
    const editor = document.getElementById("contract-document-content");
    if (editor && originalText) {
      const orig = originalText.trim();
      if (editor.innerText.includes(orig)) {
        editor.innerText = editor.innerText.replace(orig, revisedText);
      } else if (editor.innerHTML.includes(orig)) {
        editor.innerHTML = editor.innerHTML.replace(orig, revisedText);
      }
    }
    setHasUnsavedChanges(true);
    fetchContractData(true);
  };

  const getSeverityColor = (sev: string) => {
    switch (sev?.toLowerCase()) {
      case "critical":
        return "text-red-600";
      case "high":
        return "text-orange-600";
      case "medium":
        return "text-amber-600";
      case "low":
        return "text-blue-600";
      case "info":
        return "text-slate-500";
      default:
        return "text-slate-500";
    }
  };

  const getSeverityBg = (sev: string) => {
    switch (sev?.toLowerCase()) {
      case "critical":
        return "bg-red-50";
      case "high":
        return "bg-orange-50";
      case "medium":
        return "bg-amber-50";
      case "low":
        return "bg-blue-50";
      case "info":
        return "bg-slate-50";
      default:
        return "bg-slate-50";
    }
  };

  const handleAskQuestion = async () => {
    if (!contractId || !qaInput.trim() || qaLoading) return;

    const question = qaInput.trim();
    const pendingId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;

    setQaInput("");

    setQaHistory((prev) => [
      ...prev,
      {
        id: pendingId,
        question,
        answer: "",
        answerHtml: "",
        isPending: true,
        isError: false,
      },
    ]);

    setQaLoading(true);

    try {
      const response = await apiClient.askContractQuestion(
        contractId,
        question,
      );
      let answerText =
        response?.answer || response?.detail || response?.error || "No answer returned.";

      if (
        response?.citations &&
        Array.isArray(response.citations) &&
        response.citations.length > 0
      ) {
        answerText += "\n\n---\n**Citations / References:**\n";
        response.citations.forEach((c: any, idx: number) => {
          const pages = c.page_start
            ? ` (Page ${c.page_start}${c.page_end && c.page_end !== c.page_start ? `-${c.page_end}` : ""})`
            : "";
          const quote = c.content ? `\n> "${c.content}"` : "";
          answerText += `\n${idx + 1}. **Chunk ${c.chunk_id || idx + 1}**${pages}${quote}`;
        });
      }

      const answerHtml = await renderMarkdownToHtml(answerText);

      setQaHistory((prev) =>
        prev.map((item) =>
          item.id === pendingId
            ? {
                ...item,
                answer: answerText,
                answerHtml,
                isPending: false,
                isError: false,
              }
            : item,
        ),
      );
    } catch (error: any) {
      const serverDetail = error?.response?.data?.detail;
      toast.error(serverDetail || "Failed to get AI answer.");
      const errorText = serverDetail
        ? `**Error:** ${serverDetail}`
        : "Request failed. Please check your network connection and try again.";
      const errorHtml = await renderMarkdownToHtml(errorText);

      setQaHistory((prev) =>
        prev.map((item) =>
          item.id === pendingId
            ? {
                ...item,
                answer: errorText,
                answerHtml: errorHtml,
                isPending: false,
                isError: true,
              }
            : item,
        ),
      );
    } finally {
      setQaLoading(false);
    }
  };

  useEffect(() => {
    if (rightPanelTab !== "chat" || !qaThreadRef.current) return;

    qaThreadRef.current.scrollTo({
      top: qaThreadRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [qaHistory, qaLoading, rightPanelTab]);

  const quickPrompts = [
    "Rewrite indemnity to be vendor-friendly and capped.",
    "Summarize top 3 negotiation priorities in plain language.",
    "Flag hidden termination and auto-renewal risks.",
  ];

  const handleApplyQuickPrompt = (prompt: string) => {
    setQaInput(prompt);
    qaInputRef.current?.focus();
  };

  const handleExportPdf = async () => {
    if (!contractId || !htmlContent) return;

    try {
      const toastId = toast.loading("Preparing PDF for download...");
      const html2pdf = (await import("html2pdf.js")).default;

      const element = document.getElementById("contract-document-content");
      if (!element) {
        toast.dismiss(toastId);
        return;
      }

      const opt = {
        margin: 0.7,
        filename: `${contract?.company_name?.replace(/\s+/g, "_") || "contract"}_document.pdf`,
        image: { type: "jpeg" as const, quality: 0.98 },
        html2canvas: { scale: 2 },
        jsPDF: {
          unit: "in" as const,
          format: "letter" as const,
          orientation: "portrait" as const,
        },
      };

      await html2pdf()
        .set(opt as any)
        .from(element)
        .save();
      toast.success("PDF Downloaded successfully!", { id: toastId });
    } catch (e) {
      console.error("PDF Export error:", e);
      toast.error("Failed to generate PDF");
    }
  };

  if (isGenerating) {
    const steps = [
      "Invoking Contract Drafting Orchestrator...",
      "Analyzing template structure & database chunks...",
      "Researching Indian Contract Act & Kanoon legal precedents...",
      "Drafting custom clauses with writer specialist agent...",
      "Reviewing compliance & finalizing contract draft...",
    ];

    return (
      <div className="flex w-full h-[calc(100vh-70px)] bg-[#0B1437] items-center justify-center relative overflow-hidden flex-col gap-6">
        <div className="absolute w-[600px] h-[600px] bg-blue-600/20 rounded-full blur-[120px] animate-pulse"></div>
        <div
          className="absolute w-[400px] h-[400px] bg-purple-600/20 rounded-full blur-[100px] -translate-x-1/2 translate-y-1/2 animate-pulse"
          style={{ animationDelay: "1s" }}
        ></div>

        <div className="relative z-10 w-28 h-28 mb-4">
          <div className="absolute inset-0 border-4 border-blue-500/20 rounded-full"></div>
          <div className="absolute inset-0 border-[5px] border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <div className="absolute inset-3 border-4 border-purple-500/20 rounded-full"></div>
          <div className="absolute inset-3 border-[4px] border-purple-500 border-b-transparent rounded-full animate-[spin_1.5s_linear_infinite_reverse]"></div>
          <div className="absolute inset-0 flex items-center justify-center">
            <Sparkles
              className="w-8 h-8 text-blue-400 animate-pulse"
              strokeWidth={2}
            />
          </div>
        </div>

        <h2 className="relative z-10 text-[26px] font-bold text-white tracking-tight">
          Drafting Contract Sequence
        </h2>

        <div className="relative z-10 flex items-center gap-3">
          <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
          <p className="text-blue-200 text-[14px] font-medium tracking-wide transition-all min-w-[220px]">
            {steps[Math.min(loadingStep, steps.length - 1)]}
          </p>
        </div>

        <div className="relative z-10 w-72 h-1.5 bg-white/10 rounded-full overflow-hidden mt-6 shadow-[0_0_15px_rgba(59,95,229,0.3)]">
          <div
            className="h-full bg-gradient-to-r from-[#3B5FE5] to-purple-500 rounded-full transition-all duration-[1200ms] ease-out"
            style={{ width: `${Math.min((loadingStep + 1) * 20, 100)}%` }}
          ></div>
        </div>
      </div>
    );
  }

  const toggleClause = (idx: number) => {
    const newSet = new Set(expandedClauses);
    if (newSet.has(idx)) {
      newSet.delete(idx);
    } else {
      newSet.add(idx);
    }
    setExpandedClauses(newSet);
  };

  if (fetching) {
    return (
      <div className="flex w-full h-[calc(100vh-70px)] items-center justify-center bg-white flex-col gap-4">
        <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
        <p className="text-slate-500 font-bold tracking-widest text-[12px] uppercase">
          Retrieving Document & Analysis...
        </p>
      </div>
    );
  }

  return (
    <div className="flex w-full h-[calc(100vh-70px)] text-slate-900 bg-white">
      {/* Floating Pill for Selection AI Editing */}
      {floatingPill && (
        <div
          id="ai-selection-floating-pill"
          style={{
            position: "fixed",
            left: `${floatingPill.x}px`,
            top: `${floatingPill.y}px`,
            transform: "translate(-50%, -100%)",
            zIndex: 40,
          }}
          className="animate-in fade-in zoom-in-95 duration-150"
        >
          <button
            type="button"
            onClick={handleOpenSelectionEditor}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[#0B1437] hover:bg-[#1C2B62] text-white text-xs font-bold shadow-2xl border border-blue-400/40 hover:scale-105 active:scale-95 transition-all cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-blue-400 animate-pulse" />
            <span>Edit with AI</span>
          </button>
        </div>
      )}

      {/* Main Document Viewer & Editor Panel */}
      <div className="flex-[2] flex flex-col h-full border-r border-slate-200 relative min-w-0">
        {/* Document Header Toolbar */}
        <div className="flex items-center justify-between px-8 py-4 border-b border-slate-200 bg-white shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-[11px] font-bold tracking-widest text-[#0B1437] opacity-60 uppercase truncate max-w-[280px]">
              DOCUMENT /{" "}
              {contract?.original_filename ||
                contract?.markdown_file ||
                "No Document Selected"}
            </h2>
            <span
              className={`px-2.5 py-1 rounded-md text-[9px] font-bold tracking-widest uppercase transition-colors ${
                hasUnsavedChanges
                  ? "bg-amber-100 text-amber-700"
                  : "bg-[#Eef3FE] text-[#3B5FE5]"
              }`}
            >
              {hasUnsavedChanges
                ? "UNSAVED CHANGES"
                : contract?.status || "DRAFT"}
            </span>
            {pollingActive && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[9px] font-bold tracking-widest uppercase bg-blue-100 text-blue-700">
                <Loader2 className="w-3 h-3 animate-spin" /> LIVE POLLING
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleExportPdf}
              disabled={!contractId || !htmlContent}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors disabled:opacity-50 cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" /> Export PDF
            </button>

            <button
              onClick={handleSaveDraft}
              disabled={isSaving || !contractId}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer"
            >
              {isSaving ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-600" />
              ) : (
                <Save className="w-3.5 h-3.5 text-slate-600" />
              )}
              <span>Save Draft</span>
            </button>

            <button
              onClick={handleSaveAndAnalyze}
              disabled={isAnalyzing || !contractId}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold shadow-sm transition-all cursor-pointer ${
                isAnalyzing
                  ? "bg-slate-100 text-slate-400 cursor-not-allowed shadow-none"
                  : hasUnsavedChanges
                    ? "bg-[#3B5FE5] hover:bg-[#2A4AC2] text-white shadow-[0_4px_14px_rgba(59,95,229,0.3)]"
                    : "bg-[#0B1437] hover:bg-[#152458] text-white"
              }`}
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Analyzing...
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-blue-300" /> Save & Re-analyze
                </>
              )}
            </button>
          </div>
        </div>

        {/* Interactive Editor Area */}
        <div className="flex-1 overflow-y-auto px-12 py-10 relative bg-white custom-scrollbar">
          {!contractId ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-10">
              <FileText className="w-16 h-16 text-slate-200 mb-6" />
              <h3 className="text-[20px] font-bold text-slate-900 mb-2">
                No Document Loaded
              </h3>
              <p className="text-slate-500 text-[14px] max-w-sm">
                Please select a contract from your repository to view and
                edit its content.
              </p>
            </div>
          ) : (
            <div className="max-w-[780px] mx-auto space-y-12">
              <div className="text-xs text-slate-400 bg-slate-50 border border-slate-200/80 rounded-xl px-4 py-2.5 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-blue-500" />
                  <strong>Tip:</strong> Highlight any text to edit and redraft with AI.
                </span>
                <span className="text-[11px] text-slate-500 font-mono">
                  {htmlContent ? "Ready for editing" : "Loading..."}
                </span>
              </div>

              <DocumentEditor
                contract={contract}
                htmlContent={htmlContent}
                onInput={handleContentChange}
                onMouseUp={handleEditorMouseUp}
              />
              <div className="h-40"></div>
            </div>
          )}
        </div>
      </div>

      {/* Right Sidebar: Tabbed Navigation for Analysis Suggestions & Jurist Chat */}
      <div className="flex-1 min-w-[390px] max-w-[460px] bg-[#F4F7FB] overflow-hidden h-full flex flex-col shadow-[-10px_0_30px_rgba(0,0,0,0.02)] border-l border-slate-200">
        {/* Tab Headers */}
        <div className="flex items-center border-b border-slate-200 bg-white px-6 pt-3 shrink-0 gap-2">
          <button
            type="button"
            onClick={() => setRightPanelTab("analysis")}
            className={`flex items-center gap-2 pb-3 px-3 text-xs font-bold border-b-2 transition-all cursor-pointer ${
              rightPanelTab === "analysis"
                ? "border-[#3B5FE5] text-[#3B5FE5]"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            <span>Risk & Edit Suggestions</span>
            {analysis?.clauses && analysis.clauses.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[10px] bg-blue-100 text-blue-700 font-bold">
                {analysis.clauses.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setRightPanelTab("chat")}
            className={`flex items-center gap-2 pb-3 px-3 text-xs font-bold border-b-2 transition-all cursor-pointer ${
              rightPanelTab === "chat"
                ? "border-[#3B5FE5] text-[#3B5FE5]"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Bot className="w-4 h-4" />
            <span>Ask AI Jurist</span>
            {qaHistory.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[10px] bg-slate-100 text-slate-600 font-bold">
                {qaHistory.length}
              </span>
            )}
          </button>
        </div>

        {/* Tab 1: Analysis & Suggestions */}
        {rightPanelTab === "analysis" && (
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6 custom-scrollbar">
            {/* Risk Score Summary Card */}
            <div className="bg-[#0B1437] rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/10 rounded-full blur-[60px] pointer-events-none"></div>
              <div className="relative z-10 flex items-start justify-between mb-4">
                <span className="text-[10px] font-bold tracking-[0.15em] uppercase text-white/80">
                  {isAnalyzing ? "ANALYZING..." : "CONTRACT RISK PROFILE"}
                </span>
                <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-white/10 text-white border border-white/10">
                  {analysis?.overall_risk_score > 60
                    ? "High Exposure"
                    : analysis?.overall_risk_score > 30
                      ? "Moderate Exposure"
                      : "Low Risk"}
                </span>
              </div>

              <div className="flex items-baseline gap-2 mb-4">
                <span className="text-5xl font-bold tracking-tight">
                  {analysis?.overall_risk_score || 0}
                </span>
                <span className="text-sm font-medium text-white/50">/ 100</span>
              </div>

              <div className="w-full h-1.5 bg-white/10 rounded-full mb-6 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-1000 ${
                    (analysis?.overall_risk_score || 0) > 70
                      ? "bg-red-400"
                      : (analysis?.overall_risk_score || 0) > 40
                        ? "bg-amber-400"
                        : "bg-blue-400"
                  }`}
                  style={{ width: `${analysis?.overall_risk_score || 0}%` }}
                ></div>
              </div>

              {/* Counts Grid */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-white/5 rounded-xl p-2.5 border border-white/5">
                  <span className="block text-[10px] font-bold text-white/40 uppercase">
                    Critical / High
                  </span>
                  <span className="text-base font-bold text-red-300">
                    {(analysis?.critical_issues || 0) + (analysis?.high_issues || 0)}
                  </span>
                </div>
                <div className="bg-white/5 rounded-xl p-2.5 border border-white/5">
                  <span className="block text-[10px] font-bold text-white/40 uppercase">
                    Medium / Low
                  </span>
                  <span className="text-base font-bold text-blue-200">
                    {(analysis?.medium_issues || 0) + (analysis?.low_issues || 0)}
                  </span>
                </div>
              </div>
            </div>

            {/* Recommended Actions */}
            {analysis?.recommended_actions && analysis.recommended_actions.length > 0 && (
              <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
                <h4 className="text-[11px] font-bold tracking-wider uppercase text-slate-500 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                  Recommended Next Steps
                </h4>
                <ul className="space-y-2 text-xs text-slate-700">
                  {analysis.recommended_actions.map((act: string, i: number) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-600 mt-1.5 shrink-0"></span>
                      <span>{act}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Clause Analysis & Suggestions List */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-[11px] font-bold tracking-wider uppercase text-slate-500">
                  Identified Clauses & Edit Suggestions
                </h4>
                <span className="text-[10px] text-slate-400 font-semibold">
                  {analysis?.clauses?.length || 0} clauses
                </span>
              </div>

              {(!analysis?.clauses || analysis.clauses.length === 0) ? (
                <div className="bg-white rounded-2xl p-6 border border-slate-200 text-center text-xs text-slate-500">
                  No clause breakdown available yet. Click &quot;Save & Re-analyze&quot; to run analysis.
                </div>
              ) : (
                analysis.clauses.map((clause: any, i: number) => {
                  const isExpanded = expandedClauses.has(i);

                  return (
                    <div
                      key={i}
                      className="bg-white rounded-2xl p-4 shadow-sm border border-slate-200/90 hover:border-blue-300 transition-all space-y-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-start gap-2.5">
                          <div
                            className={`w-7 h-7 rounded-lg ${
                              clause.severity === "critical" || clause.severity === "high"
                                ? "bg-red-50 text-red-600"
                                : "bg-emerald-50 text-emerald-600"
                            } flex items-center justify-center shrink-0 mt-0.5`}
                          >
                            {clause.severity === "critical" || clause.severity === "high" ? (
                              <AlertTriangle className="w-4 h-4" />
                            ) : (
                              <CheckCircle2 className="w-4 h-4" />
                            )}
                          </div>
                          <div>
                            <h5 className="font-bold text-xs text-slate-900 capitalize">
                              {clause.section_title || clause.clause_type?.replaceAll("_", " ")}
                            </h5>
                            <span
                              className={`inline-block mt-1 px-2 py-0.5 ${getSeverityBg(clause.severity)} ${getSeverityColor(clause.severity)} rounded text-[9px] font-bold tracking-wider uppercase`}
                            >
                              {clause.severity}
                            </span>
                          </div>
                        </div>

                        {/* Action: Open AI Redraft Modal */}
                        <button
                          type="button"
                          onClick={() => handleOpenClauseRedraft(clause, i)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-bold transition border border-blue-200/60 shrink-0 cursor-pointer"
                        >
                          <Wand2 className="w-3.5 h-3.5 text-blue-600" />
                          <span>AI Fix</span>
                        </button>
                      </div>

                      {/* Risk snippet */}
                      <p className="text-xs text-slate-600 leading-relaxed">
                        {clause.risk_description || clause.raw_text}
                      </p>

                      {/* Expandable details */}
                      <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                        <button
                          type="button"
                          onClick={() => toggleClause(i)}
                          className="text-slate-500 hover:text-slate-800 font-semibold flex items-center gap-1"
                        >
                          <span>{isExpanded ? "Hide Details" : "Legal Grounding"}</span>
                          {isExpanded ? (
                            <ChevronUp className="w-3 h-3" />
                          ) : (
                            <ChevronDown className="w-3 h-3" />
                          )}
                        </button>

                        <span className="text-slate-400 text-[10px]">
                          {clause.applicable_statute || "Indian Contract Act"}
                        </span>
                      </div>

                      {isExpanded && (
                        <div className="pt-2 space-y-2 text-xs bg-slate-50 p-3 rounded-xl border border-slate-100 animate-in fade-in duration-200">
                          {clause.legal_reasoning && (
                            <div>
                              <span className="font-bold text-slate-700 block mb-0.5">
                                Reason & Precedents:
                              </span>
                              <p className="text-slate-600">{clause.legal_reasoning}</p>
                            </div>
                          )}
                          {clause.statute_section && (
                            <div className="flex items-center gap-1.5 text-blue-800 font-medium">
                              <Globe className="w-3 h-3 text-blue-600" />
                              <span>Section: {clause.statute_section}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Ask AI Jurist Q&A */}
        {rightPanelTab === "chat" && (
          <div className="flex-1 flex flex-col min-h-0 bg-white">
            {/* Chat Thread */}
            <div
              ref={qaThreadRef}
              className="flex-1 min-h-0 p-5 overflow-y-auto space-y-4 custom-scrollbar"
            >
              {qaHistory.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-6">
                  <div className="w-12 h-12 rounded-2xl bg-blue-50 border border-blue-200 flex items-center justify-center mb-4">
                    <Bot className="w-6 h-6 text-blue-600" />
                  </div>
                  <h4 className="text-sm font-bold text-slate-800 mb-1">
                    Ask AI Jurist
                  </h4>
                  <p className="text-xs text-slate-500 mb-6 max-w-xs leading-relaxed">
                    Ask questions grounded in the contract text, request redrafting suggestions, or verify statutory compliance.
                  </p>
                  <div className="flex flex-col gap-2 w-full max-w-xs">
                    {quickPrompts.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        onClick={() => handleApplyQuickPrompt(prompt)}
                        className="w-full px-3 py-2.5 rounded-xl bg-slate-50 hover:bg-blue-50 border border-slate-200 text-xs text-left text-slate-700 transition font-medium"
                      >
                        + {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                qaHistory.map((item) => (
                  <div key={item.id} className="space-y-3">
                    {/* User message */}
                    <div className="flex justify-end pl-8">
                      <div className="bg-[#0B1437] text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-xs shadow-sm">
                        {item.question}
                      </div>
                    </div>

                    {/* Agent message */}
                    <div className="flex justify-start pr-8 gap-2.5">
                      <div className="w-7 h-7 rounded-xl bg-blue-50 text-blue-600 border border-blue-200 flex items-center justify-center shrink-0 mt-0.5">
                        <Bot className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        {item.isPending ? (
                          <div className="flex items-center gap-2 text-xs text-slate-500 py-2">
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Retrieving contract chunks & drafting response...</span>
                          </div>
                        ) : (
                          <div
                            className={`contract-markdown markdown-body text-xs bg-slate-50 border border-slate-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm ${
                              item.isError ? "text-red-600" : "text-slate-800"
                            }`}
                            dangerouslySetInnerHTML={{ __html: item.answerHtml }}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Chat Input Composer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 shrink-0 space-y-2">
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden focus-within:ring-2 focus-within:ring-blue-500 transition">
                <textarea
                  ref={qaInputRef}
                  placeholder="Ask a question or request a clause change..."
                  value={qaInput}
                  onChange={(e) => setQaInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleAskQuestion();
                    }
                  }}
                  className="w-full h-20 resize-none outline-none text-xs text-slate-800 placeholder:text-slate-400 p-3 bg-transparent"
                />
                <div className="flex items-center justify-between px-3 pb-2.5">
                  <span className="text-[10px] text-slate-400">
                    Enter to send, Shift+Enter for newline
                  </span>
                  <button
                    onClick={handleAskQuestion}
                    disabled={!contractId || qaLoading || !qaInput.trim()}
                    className="h-8 px-3 rounded-lg bg-[#0B1437] hover:bg-[#152458] disabled:bg-slate-200 disabled:text-slate-400 text-white flex items-center justify-center gap-1.5 transition text-xs font-semibold cursor-pointer"
                  >
                    {qaLoading ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Send className="w-3.5 h-3.5" />
                    )}
                    <span>Send</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Clause Redline Modal for Suggested Fixes */}
      {activeClauseForRedraft && (
        <ClauseRedlineModal
          contractId={contractId || ""}
          clause={activeClauseForRedraft}
          isOpen={!!activeClauseForRedraft}
          onClose={() => setActiveClauseForRedraft(null)}
          onRevisionApplied={handleClauseRevisionApplied}
        />
      )}

      {/* AI Selection Modal for Highlights */}
      <AISelectionModal
        isOpen={isSelectionModalOpen}
        onClose={() => {
          setIsSelectionModalOpen(false);
          setSavedRange(null);
        }}
        selectedText={selectedSnippet}
        contractId={contractId || ""}
        onApply={handleApplySelectionReplacement}
      />
    </div>
  );
}
