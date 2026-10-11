"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { 
  ArrowLeft, Upload, FileText, Image as ImageIcon, Play, 
  CheckCircle2, AlertCircle, Loader2, Sparkles, RefreshCw, FileCheck
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";

interface CaseDocumentItem {
  id: string;
  case_id: string;
  name: string;
  storage_link: string;
  file_type: string;
  document_type?: string;
  status: string;
  date_created: string;
}

interface CaseDetail {
  id: string;
  title: string;
  description?: string;
  status: string;
  created_at: string;
  updated_at: string;
  documents: CaseDocumentItem[];
  has_analysis: boolean;
  timeline_count: number;
}

export default function CaseWorkspacePage() {
  const params = useParams();
  const caseId = params.id as string;
  const router = useRouter();

  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [agentLogs, setAgentLogs] = useState<any[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchCase = async () => {
    try {
      const data = await apiClient.getCaseDetails(caseId);
      setCaseDetail(data);
    } catch (err: any) {
      console.error("Failed to load case details", err);
      toast.error("Failed to load case details");
    } finally {
      setLoading(false);
    }
  };

  const fetchAgentLogs = async () => {
    try {
      const data = await apiClient.getCaseLogs(caseId);
      setAgentLogs(data.logs || []);
    } catch (err) {
      // Ignore transient log fetch errors
    }
  };

  useEffect(() => {
    fetchCase();
    fetchAgentLogs();
  }, [caseId]);

  // Auto poll status & agent activity logs if case or any document is processing
  useEffect(() => {
    if (!caseDetail) return;
    const isCaseProcessing = caseDetail.status === "processing";
    const hasDocProcessing = caseDetail.documents?.some(d => d.status === "processing" || d.status === "uploaded");

    if (isCaseProcessing || hasDocProcessing) {
      const timer = setInterval(() => {
        fetchCase();
        fetchAgentLogs();
      }, 3000);
      return () => clearInterval(timer);
    }
  }, [caseDetail]);

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];

    const supportedExts = [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".webp"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!supportedExts.includes(ext)) {
      toast.error(`Unsupported file type. Allowed: ${supportedExts.join(", ")}`);
      return;
    }

    setUploading(true);
    try {
      await apiClient.uploadCaseDocument(caseId, file);
      toast.success(`Uploaded "${file.name}"! Document queued for OCR & parsing.`);
      fetchCase();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to upload document");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    handleFileUpload(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleTriggerAnalysis = async () => {
    if (!caseDetail?.documents || caseDetail.documents.length === 0) {
      toast.error("Please upload at least one document before triggering analysis.");
      return;
    }

    setTriggering(true);
    try {
      await apiClient.triggerCaseAnalysis(caseId);
      toast.success("Multi-agent analysis pipeline triggered successfully!");
      fetchCase();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to trigger analysis pipeline");
    } finally {
      setTriggering(false);
    }
  };

  const getDocIcon = (fileType: string) => {
    if (fileType.includes("image")) {
      return <ImageIcon className="w-5 h-5 text-purple-600" />;
    }
    return <FileText className="w-5 h-5 text-indigo-600" />;
  };

  const getDocStatusBadge = (status: string) => {
    if (status === "completed") {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
          <CheckCircle2 className="w-3 h-3" /> Ready
        </span>
      );
    }
    if (status === "processing") {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200">
          <Loader2 className="w-3 h-3 animate-spin" /> Parsing...
        </span>
      );
    }
    if (status === "error") {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700 bg-rose-50 px-2.5 py-0.5 rounded-full border border-rose-200">
          <AlertCircle className="w-3 h-3" /> Error
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
        Uploaded
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-30">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        <span className="ml-3 text-slate-600 font-medium">Loading case details...</span>
      </div>
    );
  }

  if (!caseDetail) {
    return (
      <div className="p-8 max-w-4xl mx-auto text-center space-y-4">
        <AlertCircle className="w-12 h-12 text-rose-500 mx-auto" />
        <h2 className="text-xl font-bold text-slate-900">Case File Not Found</h2>
        <Link href="/dashboard/cases" className="text-indigo-600 font-semibold hover:underline inline-flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" /> Return to Case Files
        </Link>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Top Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard/cases"
          className="text-slate-500 hover:text-slate-900 text-sm font-semibold inline-flex items-center gap-1.5 transition"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Case Files
        </Link>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchCase}
            className="p-2 rounded-xl text-slate-500 hover:bg-slate-100 transition"
            title="Refresh case details"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          {caseDetail.has_analysis && (
            <Link
              href={`/dashboard/cases/${caseId}/results`}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-sm font-bold inline-flex items-center gap-2 shadow-xs transition"
            >
              <Sparkles className="w-4 h-4" />
              View DB Analysis Results
            </Link>
          )}
        </div>
      </div>

      {/* Case Overview Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{caseDetail.title}</h1>
            <p className="text-sm text-slate-500 mt-1">
              {caseDetail.description || "No description provided for this case file."}
            </p>
          </div>
          <div className="shrink-0">
            {caseDetail.status === "analyzed" || caseDetail.has_analysis ? (
              <span className="px-3 py-1.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 inline-flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" /> Analysis Complete
              </span>
            ) : caseDetail.status === "processing" ? (
              <span className="px-3 py-1.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200 inline-flex items-center gap-1.5">
                <Loader2 className="w-4 h-4 animate-spin" /> Pipeline Running
              </span>
            ) : (
              <span className="px-3 py-1.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200 inline-flex items-center gap-1.5">
                Awaiting Analysis
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-6 text-xs text-slate-400 font-medium pt-3 border-t border-slate-100">
          <span>ID: <code className="text-slate-700">{caseDetail.id}</code></span>
          <span>Created: {new Date(caseDetail.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })}</span>
          <span>Total Documents: <strong className="text-slate-800">{caseDetail.documents.length}</strong></span>
        </div>
      </div>

      {/* Grid: Left - Document Upload & List; Right - Pipeline Trigger Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column (2 spans): Document Upload & Document List */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Upload Dropzone */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            className="bg-white border-2 border-dashed border-slate-300 hover:border-indigo-500 transition rounded-2xl p-8 text-center space-y-4 cursor-pointer group"
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => handleFileUpload(e.target.files)}
              accept=".pdf,.jpg,.jpeg,.png,.bmp,.webp"
              className="hidden"
            />
            <div className="w-14 h-14 rounded-2xl bg-indigo-50 group-hover:bg-indigo-100 transition flex items-center justify-center mx-auto text-indigo-600">
              {uploading ? <Loader2 className="w-7 h-7 animate-spin" /> : <Upload className="w-7 h-7" />}
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-base">
                {uploading ? "Uploading document..." : "Click or Drag & Drop Documents"}
              </h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Supports PDF legal filings, FIRs, charge sheets, witness statements, and evidence photos (JPG, PNG).
              </p>
            </div>
          </div>

          {/* Uploaded Documents Table */}
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-indigo-600" />
                Case Documents ({caseDetail.documents.length})
              </h3>
              <span className="text-xs text-slate-400 font-medium">Auto-parsed on upload</span>
            </div>

            {caseDetail.documents.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">
                No documents uploaded yet. Upload PDFs or evidence photos above.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {caseDetail.documents.map((doc) => (
                  <div key={doc.id} className="p-4 px-6 flex items-center justify-between gap-4 hover:bg-slate-50 transition">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center shrink-0">
                        {getDocIcon(doc.file_type)}
                      </div>
                      <div className="min-w-0">
                        <p className="font-bold text-sm text-slate-900 truncate">{doc.name}</p>
                        <p className="text-xs text-slate-400 font-medium truncate">
                          {doc.file_type} • Uploaded {new Date(doc.date_created).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>
                    </div>

                    <div className="shrink-0 flex items-center gap-3">
                      {getDocStatusBadge(doc.status)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Trigger Analysis & Pipeline Banner */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 shrink-0">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-base">Case Pipeline Analysis</h3>
                <p className="text-xs text-slate-500">Multi-Agent Case File Orchestrator</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 p-3.5 rounded-xl border border-slate-100">
              Triggering the analysis pipeline will execute the background <strong>CaseOrchestrator</strong> deep agent loop. It performs multimodal OCR on evidence, extracts chunked text, generates chronological timelines, and compiles a structured legal report in the database.
            </p>

            <div className="space-y-2">
              <button
                onClick={handleTriggerAnalysis}
                disabled={triggering || caseDetail.status === "processing" || caseDetail.documents.length === 0}
                className="w-full bg-[#0B1437] hover:bg-[#152458] text-white font-bold py-3.5 px-4 rounded-xl text-sm flex items-center justify-center gap-2 transition shadow-sm disabled:opacity-50"
              >
                {triggering || caseDetail.status === "processing" ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Pipeline Running...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-white" />
                    Run Multi-Agent Analysis
                  </>
                )}
              </button>

              {caseDetail.documents.length === 0 && (
                <p className="text-center text-xs text-rose-500 font-medium">
                  Upload at least one document first.
                </p>
              )}
            </div>

            {caseDetail.has_analysis && (
              <div className="pt-3 border-t border-slate-100">
                <Link
                  href={`/dashboard/cases/${caseId}/results`}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 px-4 rounded-xl text-sm flex items-center justify-center gap-2 transition shadow-xs"
                >
                  <Sparkles className="w-4 h-4" />
                  View Completed Analysis
                </Link>
              </div>
            )}
          </div>

          {/* Live Agent Thinking & Tool Calling Activity Console */}
          <div className="bg-slate-900 rounded-2xl p-5 border border-slate-800 shadow-md space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <h4 className="font-mono text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Agent Thinking & Tool Execution Log
                </h4>
              </div>
              <span className="text-[10px] font-mono text-slate-400">
                {agentLogs.length} Events
              </span>
            </div>

            <div className="font-mono text-[11px] space-y-2 max-h-[300px] overflow-y-auto pr-1">
              {agentLogs.length === 0 ? (
                <p className="text-slate-500 italic py-4 text-center">
                  {caseDetail.status === "processing"
                    ? "Agent orchestrator is initializing and analyzing document chunks..."
                    : "No live agent logs recorded yet. Click 'Run Multi-Agent Analysis' to start."}
                </p>
              ) : (
                agentLogs.map((log: any, idx: number) => (
                  <div key={idx} className="space-y-0.5 border-b border-slate-800/60 pb-1.5">
                    <div className="flex items-center justify-between text-[10px] text-slate-400">
                      <span className="font-bold text-indigo-400">[{log.agent_name || "CaseOrchestrator"}]</span>
                      <span>{log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ""}</span>
                    </div>
                    <p className={`text-slate-200 break-words ${log.type === 'tool_call' ? 'text-amber-300' : log.type === 'thinking' ? 'text-cyan-300' : 'text-emerald-300'}`}>
                      <span className="font-bold uppercase text-[10px] opacity-75">[{log.type || "action"}]</span> {log.detail}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
