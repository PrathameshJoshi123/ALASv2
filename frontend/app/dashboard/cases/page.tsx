"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, FolderKanban, FileText, ChevronRight, Sparkles, AlertCircle, Clock, CheckCircle2, Loader2, X, Upload, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";

interface CaseItem {
  id: string;
  title: string;
  description?: string;
  status: string;
  created_at: string;
  documents_count: number;
  has_analysis: boolean;
}

export default function CasesPage() {
  const router = useRouter();
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const fetchCases = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getCases();
      setCases(data || []);
    } catch (err: any) {
      console.error("Failed to fetch cases", err);
      toast.error("Failed to load case files");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const filesArray = Array.from(e.target.files);
      const supportedExts = [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".webp"];
      const validFiles = filesArray.filter((file) => {
        const ext = "." + file.name.split(".").pop()?.toLowerCase();
        if (!supportedExts.includes(ext)) {
          toast.error(`Skipped unsupported file "${file.name}"`);
          return false;
        }
        return true;
      });
      setSelectedFiles((prev) => [...prev, ...validFiles]);
    }
  };

  const removeSelectedFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) {
      toast.error("Case title is required");
      return;
    }

    setSubmitting(true);
    try {
      const createdCase = await apiClient.createCase({
        title: newTitle.trim(),
        description: newDescription.trim() || undefined,
      });

      if (selectedFiles.length > 0) {
        toast.loading(`Uploading ${selectedFiles.length} initial document(s)...`, { id: "upload-toast" });
        for (const file of selectedFiles) {
          await apiClient.uploadCaseDocument(createdCase.id, file);
        }
        toast.dismiss("upload-toast");
      }

      toast.success("Case file created successfully!");
      setNewTitle("");
      setNewDescription("");
      setSelectedFiles([]);
      setShowModal(false);
      
      // Redirect to the newly created case workspace
      router.push(`/dashboard/cases/${createdCase.id}`);
    } catch (err: any) {
      toast.dismiss("upload-toast");
      toast.error(err.response?.data?.detail || "Failed to create case");
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status: string, hasAnalysis: boolean) => {
    if (status === "analyzed" || hasAnalysis) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3.5 h-3.5" />
          Analyzed
        </span>
      );
    }
    if (status === "processing") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Analyzing Pipeline...
        </span>
      );
    }
    if (status === "error") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          <AlertCircle className="w-3.5 h-3.5" />
          Error
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        <Clock className="w-3.5 h-3.5" />
        Draft / Created
      </span>
    );
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
              <FolderKanban className="w-5 h-5 text-indigo-600" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900">Case File Analysis</h1>
          </div>
          <p className="text-slate-500 text-sm">
            Upload case files (PDF filings, FIRs, charge sheets & evidence photos), trigger multi-agent pipeline, and view structured database analysis.
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="bg-[#0B1437] text-white hover:bg-[#152458] px-4 py-2.5 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition shadow-xs shrink-0"
        >
          <Plus className="w-4 h-4" />
          New Case File
        </button>
      </div>

      {/* Main Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20 bg-white rounded-2xl border border-slate-200/80">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <span className="ml-3 text-slate-600 font-medium">Loading case files...</span>
        </div>
      ) : cases.length === 0 ? (
        <div className="text-center py-16 px-4 bg-white rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div className="w-16 h-16 rounded-full bg-indigo-50 flex items-center justify-center mx-auto">
            <FolderKanban className="w-8 h-8 text-indigo-600" />
          </div>
          <div className="max-w-md mx-auto space-y-1">
            <h3 className="text-lg font-bold text-slate-900">No Case Files Found</h3>
            <p className="text-sm text-slate-500">
              Create your first case file to start uploading documents and running automated multi-agent legal analysis.
            </p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="bg-[#0B1437] text-white hover:bg-[#152458] px-5 py-2.5 rounded-xl text-sm font-bold inline-flex items-center gap-2 shadow-xs transition"
          >
            <Plus className="w-4 h-4" />
            Create First Case
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cases.map((c) => (
            <div
              key={c.id}
              className="bg-white rounded-2xl border border-slate-200/80 p-6 flex flex-col justify-between hover:shadow-md transition group"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-bold text-slate-900 text-lg group-hover:text-indigo-600 transition line-clamp-1">
                    {c.title}
                  </h2>
                  {getStatusBadge(c.status, c.has_analysis)}
                </div>

                <p className="text-slate-500 text-sm line-clamp-2 min-h-[40px]">
                  {c.description || "No description provided for this case file."}
                </p>

                <div className="flex items-center gap-4 text-xs font-medium text-slate-400 pt-2 border-t border-slate-100">
                  <span className="flex items-center gap-1 text-slate-600">
                    <FileText className="w-3.5 h-3.5" />
                    {c.documents_count} {c.documents_count === 1 ? "Document" : "Documents"}
                  </span>
                  <span>•</span>
                  <span>{new Date(c.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-5">
                <Link
                  href={`/dashboard/cases/${c.id}`}
                  className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-800 py-2 px-3 rounded-lg text-xs font-bold text-center transition flex items-center justify-center gap-1"
                >
                  Manage Docs
                </Link>
                {c.has_analysis || c.status === "analyzed" ? (
                  <Link
                    href={`/dashboard/cases/${c.id}/results`}
                    className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-2 px-3 rounded-lg text-xs font-bold text-center transition flex items-center justify-center gap-1 shadow-2xs"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    View Results
                  </Link>
                ) : (
                  <Link
                    href={`/dashboard/cases/${c.id}`}
                    className="flex-1 bg-[#0B1437] hover:bg-[#152458] text-white py-2 px-3 rounded-lg text-xs font-bold text-center transition flex items-center justify-center gap-1"
                  >
                    Run Pipeline <ChevronRight className="w-3.5 h-3.5" />
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* New Case Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-2xs p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl border border-slate-100">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-2">
                <FolderKanban className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-lg text-slate-900">Create New Legal Case File</h3>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateCase} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Case Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. State of Maharashtra vs. John Doe"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Case Description / Background
                </label>
                <textarea
                  rows={3}
                  placeholder="e.g. Homicide investigation involving forensic ballistics, FIR statement, and photo evidence."
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Attach Initial Case Documents (Optional)
                </label>
                <div className="border border-dashed border-slate-300 hover:border-indigo-500 transition rounded-xl p-4 text-center cursor-pointer relative bg-slate-50">
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.jpg,.jpeg,.png,.bmp,.webp"
                    onChange={handleFileChange}
                    className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                  />
                  <div className="flex items-center justify-center gap-2 text-indigo-600 font-semibold text-xs">
                    <Upload className="w-4 h-4" />
                    <span>Choose PDFs or Evidence Images</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">Supports PDF, JPG, PNG, WEBP</p>
                </div>

                {selectedFiles.length > 0 && (
                  <div className="mt-2.5 space-y-1.5 max-h-32 overflow-y-auto">
                    {selectedFiles.map((file, idx) => (
                      <div key={idx} className="flex items-center justify-between text-xs bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200">
                        <span className="truncate font-medium text-slate-700 max-w-[280px]">{file.name}</span>
                        <button
                          type="button"
                          onClick={() => removeSelectedFile(idx)}
                          className="text-slate-400 hover:text-rose-600 transition p-0.5"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-600 hover:bg-slate-100 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="bg-[#0B1437] hover:bg-[#152458] text-white px-5 py-2 rounded-xl text-sm font-bold transition flex items-center gap-2 shadow-xs disabled:opacity-50"
                >
                  {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  Create Case File
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
