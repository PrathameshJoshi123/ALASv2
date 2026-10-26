"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Upload,
  FileText,
  Image as ImageIcon,
  Play,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  FolderKanban,
  ExternalLink,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

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

  useEffect(() => {
    if (!caseDetail) return;
    const isCaseProcessing = caseDetail.status === "processing";
    const hasDocProcessing = caseDetail.documents?.some(
      (d) => d.status === "processing" || d.status === "uploaded",
    );

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
      toast.success(`Uploaded "${file.name}"!`);
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
      toast.success("Litigation analysis pipeline triggered successfully!");
      fetchCase();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to trigger analysis pipeline");
    } finally {
      setTriggering(false);
    }
  };

  const getDocStatusBadge = (status: string) => {
    if (status === "completed") {
      return <Badge variant="success">Parsed</Badge>;
    }
    if (status === "processing") {
      return <Badge variant="info">Parsing...</Badge>;
    }
    if (status === "error") {
      return <Badge variant="destructive">Error</Badge>;
    }
    return <Badge variant="outline">Uploaded</Badge>;
  };

  if (loading) {
    return (
      <div className="p-16 flex flex-col items-center justify-center text-xs text-muted-foreground gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
        <span>Loading case workspace...</span>
      </div>
    );
  }

  if (!caseDetail) {
    return (
      <div className="p-8 max-w-4xl mx-auto text-center space-y-4">
        <AlertCircle className="w-12 h-12 text-destructive mx-auto" />
        <h2 className="text-xl font-bold text-foreground">Case File Not Found</h2>
        <Button variant="outline" size="sm" onClick={() => router.push("/dashboard/cases")}>
          <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Return to Case Files
        </Button>
      </div>
    );
  }

  return (
    <div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8">
      {/* 1. Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <button
            onClick={() => router.push("/dashboard/cases")}
            className="inline-flex items-center text-xs font-semibold text-muted-foreground hover:text-foreground mb-2 gap-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Case Files</span>
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              {caseDetail.title}
            </h1>
            <Badge variant="outline">
              {caseDetail.documents?.length || 0} Exhibits
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
            {caseDetail.description || "Litigation matter records under examination."}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchCase}
            className="text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Refresh
          </Button>

          {caseDetail.has_analysis || caseDetail.status === "analyzed" ? (
            <Button
              variant="default"
              size="sm"
              onClick={() => router.push(`/dashboard/cases/${caseId}/results`)}
              className="text-xs font-semibold"
            >
              <span>View Case Intelligence & Timeline</span>
            </Button>
          ) : (
            <Button
              variant="default"
              size="sm"
              onClick={handleTriggerAnalysis}
              loading={triggering || caseDetail.status === "processing"}
              className="text-xs font-semibold"
            >
              <Play className="w-3.5 h-3.5 mr-1.5" />
              <span>Trigger Multi-Doc Analysis</span>
            </Button>
          )}
        </div>
      </div>

      {/* 2. Upload Dropzone & Document Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-sm font-semibold">Exhibits & Filings</CardTitle>
              <CardDescription className="text-xs">
                Petitions, charge sheets, contracts, and evidentiary attachments
              </CardDescription>
            </div>
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,.jpg,.jpeg,.png,.bmp,.webp"
              onChange={(e) => handleFileUpload(e.target.files)}
              className="hidden"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              loading={uploading}
              className="text-xs"
            >
              <Upload className="w-3.5 h-3.5 mr-1.5" />
              Upload Exhibit
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {caseDetail.documents.length === 0 ? (
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => fileInputRef.current?.click()}
                className="p-12 text-center border-2 border-dashed border-border m-6 rounded-lg cursor-pointer hover:bg-muted/30 transition-colors"
              >
                <Upload className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-xs font-medium text-foreground">
                  Drag and drop exhibits here or click to browse
                </p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  PDF, scanned JPEG/PNG supported
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Document Name</TableHead>
                    <TableHead className="text-xs">Format</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-xs">Added On</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {caseDetail.documents.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell className="font-semibold text-xs text-foreground py-3">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                          <span className="truncate max-w-[280px]">{doc.name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground py-3 uppercase">
                        {doc.file_type?.split("/")[1] || "PDF"}
                      </TableCell>
                      <TableCell className="py-3">
                        {getDocStatusBadge(doc.status)}
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
            )}
          </CardContent>
        </Card>

        {/* Matter Intelligence & Status Panel */}
        <div className="space-y-6">
          <Card className="shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Litigation Pipeline</CardTitle>
              <CardDescription className="text-xs">
                Multi-agent cross-document ingestion
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 pt-0">
              <div className="p-3 rounded-md border border-border bg-muted/30 space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-muted-foreground">OCR & Text Extraction</span>
                  <Badge variant="success" className="text-[10px]">Active</Badge>
                </div>
              </div>
              <div className="p-3 rounded-md border border-border bg-muted/30 space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-muted-foreground">Chronological Timeline</span>
                  <Badge variant="outline" className="text-[10px]">{caseDetail.timeline_count || 0} Events</Badge>
                </div>
              </div>
              <div className="p-3 rounded-md border border-border bg-muted/30 space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-muted-foreground">Cross-Doc Contradictions</span>
                  <Badge variant="outline" className="text-[10px]">RAG Ready</Badge>
                </div>
              </div>

              {caseDetail.has_analysis && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => router.push(`/dashboard/cases/${caseId}/results`)}
                  className="w-full text-xs mt-2"
                >
                  Open Analysis Suite
                </Button>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
