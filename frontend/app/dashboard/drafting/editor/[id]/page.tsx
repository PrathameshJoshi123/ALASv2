"use client";

import { useState, useEffect, useCallback, useRef, Suspense } from "react";
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
  Printer,
  Wand2,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  ArrowLeft,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { useSearchParams, useParams, useRouter } from "next/navigation";
import { marked } from "marked";
import DOMPurify from "dompurify";
import React from "react";
import { ClauseRedlineModal } from "@/components/dashboard/ClauseRedlineModal";
import { AISelectionModal } from "@/components/dashboard/AISelectionModal";
import { DraftingStreamConsole } from "@/components/dashboard/DraftingStreamConsole";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

function cleanMarkdownForRendering(raw: string): string {
  if (!raw) return "";
  let cleaned = raw;
  cleaned = cleaned.replace(/^[ \t]*```[a-zA-Z0-9_-]*[ \t]*$/gm, "");
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n");
  return cleaned.trim();
}

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
    const hasH1InContent = /^\s*<h1[\s>]/i.test(htmlContent);

    return (
      <div
        id="contract-document-content"
        contentEditable
        suppressContentEditableWarning
        onInput={onInput}
        onMouseUp={onMouseUp}
        onKeyUp={onMouseUp}
        style={{ backgroundColor: "#ffffff", color: "#0f172a" }}
        className="outline-none focus:bg-slate-50/50 p-6 rounded-xl transition-colors selection:bg-blue-100 selection:text-blue-900 border border-transparent focus:border-border bg-white text-slate-900"
      >
        {!hasH1InContent && (
          <h1 className="text-2xl font-bold text-slate-900 mb-6 tracking-tight">
            {(
              contract?.contract_title ||
              contract?.title ||
              contract?.original_filename ||
              contract?.markdown_file ||
              "CONTRACT_AGREEMENT"
            )
              ?.split(".")[0]
              ?.replaceAll("_", " ")}
          </h1>
        )}

        <div
          className="contract-markdown markdown-body max-w-none"
          style={{ backgroundColor: "#ffffff", color: "#0f172a" }}
        >
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

function DraftingEditorInner() {
  const router = useRouter();
  const routeParams = useParams();
  const searchParams = useSearchParams();

  const paramId = routeParams?.id as string;
  const queryId = searchParams.get("id");
  const rawId = paramId && paramId !== "editor" ? paramId : queryId;

  const [contractId, setContractId] = useState<string | null>(() => {
    return rawId && rawId !== "undefined" && rawId !== "null" ? rawId : null;
  });

  const [isGenerating, setIsGenerating] = useState(() => {
    return searchParams.get("generating") === "true";
  });

  const [contract, setContract] = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [htmlContent, setHtmlContent] = useState<string>("");
  const [fetching, setFetching] = useState(
    !!(rawId && rawId !== "undefined" && rawId !== "null"),
  );
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
  const [expandedClauses, setExpandedClauses] = useState<Set<number>>(new Set());
  const qaThreadRef = useRef<HTMLDivElement | null>(null);
  const qaInputRef = useRef<HTMLTextAreaElement | null>(null);

  const renderMarkdownToHtml = useCallback(async (content: string) => {
    try {
      marked.setOptions({
        gfm: true,
        breaks: true,
      });

      const cleaned = cleanMarkdownForRendering(content);
      const rendered = marked.parse(cleaned);
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
  }, [
    analysis?.analysis_markdown,
    contract?.analysis_markdown,
    contract?.analysis?.analysis_markdown,
    renderMarkdownToHtml,
  ]);

  const fetchContractData = useCallback(
    async (isPolling = false, targetId?: string) => {
      const activeId = targetId || contractId;
      if (!activeId || activeId === "undefined" || activeId === "null") return;
      try {
        if (!isPolling) setFetching(true);
        const [contractData, analysisData] = await Promise.all([
          apiClient.getContractDetails(activeId),
          apiClient.getContractAnalysis(activeId),
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

  // Dynamically resolve contractId if only taskId is provided
  useEffect(() => {
    if (!contractId && taskId) {
      apiClient.getProcessingStatus("undefined", taskId).then((res) => {
        if (res?.document_id) {
          setContractId(res.document_id);
          fetchContractData(false, res.document_id);
        }
      });
    }
  }, [contractId, taskId, fetchContractData]);

  // Handle Document Text Selection for AI Assist
  const handleMouseUp = () => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
      setFloatingPill(null);
      return;
    }

    const text = selection.toString().trim();
    if (text.length > 5) {
      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      setFloatingPill({
        text,
        x: rect.left + rect.width / 2,
        y: rect.top - 10,
        range: range.cloneRange(),
      });
    } else {
      setFloatingPill(null);
    }
  };

  const handleDocumentChange = () => {
    setHasUnsavedChanges(true);
  };

  const handleSave = async () => {
    const editorEl = document.getElementById("contract-document-content");
    if (!editorEl || !contractId) return;

    setIsSaving(true);
    try {
      const textContent = editorEl.innerText;
      await apiClient.saveContractContent(contractId, textContent);
      setHasUnsavedChanges(false);
      toast.success("Document draft saved successfully");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to save draft");
    } finally {
      setIsSaving(false);
    }
  };

  const [isExporting, setIsExporting] = useState(false);

  const handleDownloadPDF = async () => {
    const editorEl = document.getElementById("contract-document-content");
    if (!editorEl) {
      toast.error("Contract document content is not available for export");
      return;
    }

    setIsExporting(true);
    const toastId = toast.loading("Compiling institutional legal PDF...");

    try {
      const pdfMakeModule = await import("pdfmake/build/pdfmake");
      const pdfFontsModule = await import("pdfmake/build/vfs_fonts");
      const htmlToPdfmakeModule = await import("html-to-pdfmake");

      const pdfMake = (pdfMakeModule as any).default || pdfMakeModule;
      const pdfFonts = (pdfFontsModule as any).default || pdfFontsModule;
      const htmlToPdfmake = (htmlToPdfmakeModule as any).default || htmlToPdfmakeModule;

      pdfMake.vfs = pdfFonts.pdfMake ? pdfFonts.pdfMake.vfs : pdfFonts;

      const rawTitle =
        contract?.contract_title ||
        contract?.title ||
        contract?.original_filename ||
        contract?.markdown_file ||
        "Legal_Contract";

      const cleanTitle = rawTitle
        .replace(/\.[^/.]+$/, "")
        .replace(/[^a-zA-Z0-9_\-\s]/g, "")
        .trim()
        .replace(/\s+/g, "_");

      const filename = `${cleanTitle || "Legal_Contract"}.pdf`;

      // Convert HTML content into vector PDF definitions (Zero canvas / No rasterization)
      const converted = htmlToPdfmake(editorEl.innerHTML);

      const docDefinition: any = {
        content: converted,
        defaultStyle: {
          font: "Roboto",
          fontSize: 10,
          lineHeight: 1.5,
          color: "#0f172a",
        },
        styles: {
          "html-h1": {
            fontSize: 18,
            bold: true,
            margin: [0, 8, 0, 12],
            color: "#0f172a",
          },
          "html-h2": {
            fontSize: 13,
            bold: true,
            margin: [0, 14, 0, 6],
            color: "#0f172a",
          },
          "html-h3": {
            fontSize: 11,
            bold: true,
            margin: [0, 10, 0, 4],
            color: "#1e293b",
          },
          "html-p": {
            margin: [0, 0, 0, 8],
            alignment: "justify",
          },
          "html-li": {
            margin: [0, 0, 0, 3],
          },
        },
        pageMargins: [40, 50, 40, 50],
        pageSize: "A4",
        header: function () {
          return {
            text: "ALAS LEGAL OS • CONFIDENTIAL LEGAL DRAFT",
            alignment: "right",
            fontSize: 8,
            color: "#94a3b8",
            margin: [40, 20, 40, 0],
          };
        },
        footer: function (currentPage: number, pageCount: number) {
          return {
            columns: [
              { text: cleanTitle.replaceAll("_", " "), fontSize: 8, color: "#94a3b8" },
              { text: `Page ${currentPage} of ${pageCount}`, alignment: "right", fontSize: 8, color: "#94a3b8" },
            ],
            margin: [40, 0, 40, 20],
          };
        },
      };

      pdfMake.createPdf(docDefinition).download(filename);
      toast.success("PDF downloaded successfully", { id: toastId });
    } catch (err) {
      console.error("PDF export error:", err);
      toast.error("Vector export fallback: Opening print view...", { id: toastId });
      window.print();
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-56px)] bg-background overflow-hidden">
      {/* 1. Editor Control Header */}
      <div className="h-12 border-b border-border bg-card px-6 flex items-center justify-between shrink-0 no-print">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/dashboard/drafting")}
            className="text-xs h-8 px-2"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            <span>Drafting Studio</span>
          </Button>
          <div className="h-4 w-px bg-border" />
          <span className="font-semibold text-xs text-foreground truncate max-w-sm">
            {contract?.original_filename || contract?.markdown_file || "Drafting Document"}
          </span>
          {hasUnsavedChanges && (
            <Badge variant="warning" className="text-[10px]">
              Unsaved Changes
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => window.print()}
            title="Print or Save as PDF via browser"
            className="text-xs h-8 px-2.5 text-muted-foreground hover:text-foreground border border-border"
          >
            <Printer className="w-3.5 h-3.5 mr-1.5" />
            <span>Print</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadPDF}
            disabled={isExporting}
            className="text-xs h-8"
          >
            {isExporting ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <Download className="w-3.5 h-3.5 mr-1.5" />
            )}
            <span>{isExporting ? "Exporting..." : "Export PDF"}</span>
          </Button>

          <Button
            variant="default"
            size="sm"
            onClick={handleSave}
            loading={isSaving}
            className="text-xs h-8"
          >
            <Save className="w-3.5 h-3.5 mr-1.5" />
            Save Changes
          </Button>
        </div>
      </div>

      {/* 2. Main Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* Document Editor Area */}
        <div className="flex-1 overflow-y-auto p-8 lg:p-12 custom-scrollbar bg-card">
          <div className="max-w-3xl mx-auto bg-card rounded-lg border border-border p-8 lg:p-12 shadow-sm min-h-[800px] document-printable">
            {isGenerating ? (
              <DraftingStreamConsole
                contractId={contractId || ""}
                taskId={taskId}
                prompt={searchParams.get("prompt")}
                onComplete={(resolvedDocId) => {
                  setIsGenerating(false);
                  if (resolvedDocId) {
                    setContractId(resolvedDocId);
                    fetchContractData(false, resolvedDocId);
                  } else if (contractId) {
                    fetchContractData(false, contractId);
                  }
                }}
              />
            ) : fetching ? (
              <div className="py-24 text-center text-xs text-muted-foreground flex flex-col items-center justify-center gap-3">
                <Loader2 className="w-6 h-6 animate-spin text-primary" />
                <span>Loading agreement editor...</span>
              </div>
            ) : (
              <DocumentEditor
                contract={contract}
                htmlContent={htmlContent}
                onInput={handleDocumentChange}
                onMouseUp={handleMouseUp}
              />
            )}
          </div>
        </div>

        {/* Floating AI Assist Action Pill */}
        {floatingPill && !isGenerating && (
          <div
            style={{
              position: "fixed",
              left: `${floatingPill.x}px`,
              top: `${floatingPill.y}px`,
              transform: "translate(-50%, -100%)",
            }}
            className="z-50 no-print flex items-center gap-1.5 bg-slate-900 text-white px-3 py-1.5 rounded-full shadow-lg border border-slate-700 animate-in fade-in"
          >
            <button
              onClick={() => {
                setSelectedSnippet(floatingPill.text);
                setSavedRange(floatingPill.range);
                setIsSelectionModalOpen(true);
                setFloatingPill(null);
              }}
              className="text-xs font-semibold flex items-center gap-1 hover:text-blue-300 transition-colors"
            >
              <Wand2 className="w-3.5 h-3.5 text-blue-400" />
              <span>Redraft with AI</span>
            </button>
            <button
              onClick={() => setFloatingPill(null)}
              className="text-slate-400 hover:text-white ml-1"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        )}

        {/* Right Compliance & Suggestions Panel */}
        <div className="w-80 lg:w-96 border-l border-border bg-muted/20 flex flex-col shrink-0 overflow-hidden no-print">
          <div className="p-3 border-b border-border bg-card flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Statutory Compliance
            </span>
            <Badge variant="outline" className="text-[10px]">
              ICA 1872
            </Badge>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="p-3.5 rounded-md border border-border bg-card shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                <ShieldAlert className="w-4 h-4 text-emerald-600" />
                <span>Section 27 (Non-Compete) Audit</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Indian Contract Act Section 27 renders post-employment non-competes void. Ensure restrictive covenants are strictly limited to non-solicitation of clients during term.
              </p>
            </div>

            <div className="p-3.5 rounded-md border border-border bg-card shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                <ShieldAlert className="w-4 h-4 text-emerald-600" />
                <span>Section 74 (Liquidated Damages)</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Penalties disguised as liquidated damages are unenforceable. Clause must represent a genuine pre-estimate of loss.
              </p>
            </div>

            <div className="p-3.5 rounded-md border border-border bg-card shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                <ShieldAlert className="w-4 h-4 text-emerald-600" />
                <span>Section 28 (Arbitration Seat)</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Agreements in restraint of legal proceedings are void unless saved by the statutory arbitration exception.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* AI Selection Modal */}
      {isSelectionModalOpen && (
        <AISelectionModal
          isOpen={isSelectionModalOpen}
          onClose={() => setIsSelectionModalOpen(false)}
          selectedText={selectedSnippet}
          contractId={contractId || ""}
          onApply={(revisedText) => {
            if (savedRange) {
              savedRange.deleteContents();
              savedRange.insertNode(document.createTextNode(revisedText));
              handleDocumentChange();
            }
          }}
        />
      )}
    </div>
  );
}

export default function DraftingEditorPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center">
          <div className="flex items-center gap-2 text-slate-500 text-sm">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Loading editor...</span>
          </div>
        </div>
      }
    >
      <DraftingEditorInner />
    </Suspense>
  );
}
