"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Plus,
  FolderKanban,
  FileText,
  ChevronRight,
  Clock,
  CheckCircle2,
  Loader2,
  Upload,
  Trash2,
  AlertCircle,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

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
        toast.loading(`Uploading ${selectedFiles.length} initial document(s)...`, {
          id: "upload-toast",
        });
        for (const file of selectedFiles) {
          await apiClient.uploadCaseDocument(createdCase.id, file);
        }
        toast.dismiss("upload-toast");
      }

      toast.success("Case file initialized successfully!");
      setNewTitle("");
      setNewDescription("");
      setSelectedFiles([]);
      setShowModal(false);

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
      return <Badge variant="success">Analyzed</Badge>;
    }
    if (status === "processing") {
      return <Badge variant="info">In Review</Badge>;
    }
    if (status === "error") {
      return <Badge variant="destructive">Error</Badge>;
    }
    return <Badge variant="outline">Draft Matter</Badge>;
  };

  return (
    <div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
            <span>Litigation Management</span> / <span>Case Files</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Case Files & Multi-Document Repository
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Organize litigation filings, FIRs, witness testimonies, and cross-examine evidence with automated event chronologies.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="default"
            onClick={() => setShowModal(true)}
            className="text-xs"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Create Case File
          </Button>
        </div>
      </div>

      {/* 2. Cases Grid */}
      {loading ? (
        <div className="p-16 flex flex-col items-center justify-center text-xs text-muted-foreground gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
          <span>Loading litigation case files...</span>
        </div>
      ) : cases.length === 0 ? (
        <Card className="shadow-sm border-dashed p-12 text-center space-y-4">
          <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center mx-auto text-muted-foreground">
            <FolderKanban className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-foreground">No Case Files Yet</h3>
            <p className="text-xs text-muted-foreground max-w-md mx-auto">
              Create your first litigation matter to upload multiple legal documents, generate factual timelines, and run cross-document Q&A.
            </p>
          </div>
          <Button
            variant="default"
            size="sm"
            onClick={() => setShowModal(true)}
            className="text-xs"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Create Case Matter
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cases.map((c) => (
            <Card
              key={c.id}
              onClick={() => router.push(`/dashboard/cases/${c.id}`)}
              className="cursor-pointer hover:border-slate-400/80 transition-all shadow-sm flex flex-col justify-between"
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <CardTitle className="text-sm font-bold text-foreground line-clamp-1">
                      {c.title}
                    </CardTitle>
                    <p className="text-[11px] text-muted-foreground">
                      Created: {new Date(c.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  {getStatusBadge(c.status, c.has_analysis)}
                </div>
                <CardDescription className="text-xs line-clamp-2 mt-2 leading-relaxed">
                  {c.description || "Litigation matter records under examination."}
                </CardDescription>
              </CardHeader>

              <CardContent className="pt-0 border-t border-border/60 py-3 flex items-center justify-between text-xs">
                <span className="font-semibold text-muted-foreground">
                  {c.documents_count || 0} Exhibits / Filings
                </span>
                <span className="text-accent hover:underline font-semibold flex items-center gap-1">
                  <span>Workspace</span>
                  <ChevronRight className="w-3 h-3" />
                </span>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* 3. Create Case Modal (Shadcn Dialog) */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogHeader>
          <DialogTitle>Initialize New Case File</DialogTitle>
          <DialogDescription>
            Set up a litigation matter to index petitions, affidavits, and documentary evidence.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleCreateCase} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-foreground">
              Case Matter Title *
            </label>
            <Input
              type="text"
              placeholder="e.g. State vs. Sharma & Ors. (Commercial Suit 402/2026)"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="text-xs h-9"
              required
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-foreground">
              Matter Summary / Scope
            </label>
            <Textarea
              placeholder="Brief summary of dispute, parties, forum (e.g. High Court of Delhi), and key relief sought..."
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              rows={3}
              className="text-xs resize-none"
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-foreground">
              Attach Initial Filings / Exhibits (Optional)
            </label>
            <div className="border border-dashed border-border rounded-md p-4 text-center hover:bg-muted/30 cursor-pointer">
              <input
                type="file"
                multiple
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileChange}
                className="hidden"
                id="case-doc-upload"
              />
              <label htmlFor="case-doc-upload" className="cursor-pointer block">
                <Upload className="w-5 h-5 mx-auto text-muted-foreground mb-1" />
                <span className="text-xs font-semibold text-foreground">
                  Select PDFs or Scanned Exhibits
                </span>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  PDF, JPG, PNG supported
                </p>
              </label>
            </div>

            {selectedFiles.length > 0 && (
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {selectedFiles.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between text-xs px-2.5 py-1 rounded bg-muted text-foreground"
                  >
                    <span className="truncate max-w-[280px]">{f.name}</span>
                    <button
                      type="button"
                      onClick={() => removeSelectedFile(i)}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowModal(false)}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="default"
              size="sm"
              loading={submitting}
              className="text-xs"
            >
              Initialize Matter
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}
