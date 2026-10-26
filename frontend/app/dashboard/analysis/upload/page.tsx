"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  UploadCloud,
  FileText,
  ArrowLeft,
  CheckCircle2,
  Scale,
  Loader2,
  ShieldAlert,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function ContractUploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [counterparty, setCounterparty] = useState("");
  const [companyName, setCompanyName] = useState("Lexington & Co");
  const [contractType, setContractType] = useState("Non-Disclosure Agreement (NDA)");
  const [customPrompt, setCustomPrompt] = useState("");
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [uploading, setUploading] = useState(false);

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.size > 50 * 1024 * 1024) {
        toast.error("File size exceeds 50MB limit");
        return;
      }
      setFile(droppedFile);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (selected.size > 50 * 1024 * 1024) {
        toast.error("File size exceeds 50MB limit");
        return;
      }
      setFile(selected);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      toast.error("Please select a contract document (PDF or TXT)");
      return;
    }

    setUploading(true);
    const toastId = toast.loading("Uploading and initiating legal audit...");

    try {
      const res = await apiClient.uploadContract(file, {
        company_name: companyName,
        counterparty_name: counterparty || "TBD",
        contract_type: contractType,
        contract_prompt: customPrompt || undefined,
        auto_analyze: autoAnalyze,
      });

      toast.success("Contract uploaded successfully!", { id: toastId });
      const contractId = res?.contract_id || res?.id;
      if (contractId) {
        router.push(`/dashboard/analysis/${contractId}`);
      } else {
        router.push("/dashboard/analysis");
      }
    } catch (err: any) {
      console.error("Upload error", err);
      toast.error(err?.response?.data?.detail || "Failed to upload contract", {
        id: toastId,
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-8 lg:p-10 max-w-4xl mx-auto space-y-8">
      {/* 1. Header */}
      <div className="flex items-center justify-between border-b border-border pb-6">
        <div>
          <button
            onClick={() => router.push("/dashboard/analysis")}
            className="inline-flex items-center text-xs font-semibold text-muted-foreground hover:text-foreground mb-2 gap-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Analysis Repository</span>
          </button>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Contract Intake & Analysis Setup
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Upload commercial contracts for automated clause extraction, liability shifts, and Section 27/74 ICA audit.
          </p>
        </div>
      </div>

      {/* 2. Upload Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Document File</CardTitle>
            <CardDescription className="text-xs">
              Upload PDF or TXT contract (maximum file size: 50MB)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".pdf,.txt"
              className="hidden"
            />

            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-border rounded-lg p-10 text-center hover:bg-muted/30 cursor-pointer transition-colors"
            >
              <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center mx-auto mb-3 text-muted-foreground">
                <UploadCloud className="w-6 h-6" />
              </div>
              {file ? (
                <div className="space-y-1">
                  <p className="font-semibold text-xs text-foreground flex items-center justify-center gap-1.5">
                    <FileText className="w-4 h-4 text-accent" />
                    <span>{file.name}</span>
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB • Ready for audit
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-foreground">
                    Click to browse or drop contract file here
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    PDF, TXT supported (Max 50MB)
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Matter Metadata</CardTitle>
            <CardDescription className="text-xs">
              Configure counterparty and statutory review parameters
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">
                  Contract Classification
                </label>
                <select
                  value={contractType}
                  onChange={(e) => setContractType(e.target.value)}
                  className="w-full h-9 px-3 rounded-md border border-input bg-background text-xs font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="Non-Disclosure Agreement (NDA)">Non-Disclosure Agreement (NDA)</option>
                  <option value="Master Services Agreement (MSA)">Master Services Agreement (MSA)</option>
                  <option value="Commercial Lease Agreement">Commercial Lease Agreement</option>
                  <option value="Employment Contract">Employment Contract</option>
                  <option value="Software License / SaaS Agreement">Software License / SaaS Agreement</option>
                  <option value="Vendor / Procurement Agreement">Vendor / Procurement Agreement</option>
                  <option value="Custom Commercial Contract">Custom Commercial Contract</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">
                  Counterparty Legal Name
                </label>
                <Input
                  type="text"
                  placeholder="e.g. Acme Corp India Pvt Ltd"
                  value={counterparty}
                  onChange={(e) => setCounterparty(e.target.value)}
                  className="text-xs h-9"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-foreground">
                Represented Entity (Client)
              </label>
              <Input
                type="text"
                placeholder="e.g. Lexington & Co Client"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="text-xs h-9"
              />
            </div>

            <div className="p-4 rounded-md border border-border bg-muted/40 space-y-2">
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoAnalyze}
                  onChange={(e) => setAutoAnalyze(e.target.checked)}
                  className="rounded border-border text-accent focus:ring-ring w-4 h-4"
                />
                <span className="text-xs font-semibold text-foreground">
                  Automatically run Indian Law (ICA 1872) & Kanoon Precedent Audit
                </span>
              </label>
              <p className="text-[11px] text-muted-foreground pl-6">
                Enables automated detection of restrictive covenants (Sec 27), penal liquidated damages (Sec 74), and jurisdictional restrictions (Sec 28).
              </p>
            </div>
          </CardContent>
        </Card>

        <div className="flex items-center justify-end gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => router.push("/dashboard/analysis")}
            className="text-xs"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="default"
            loading={uploading}
            disabled={!file || uploading}
            className="text-xs"
          >
            Upload and Begin Audit
          </Button>
        </div>
      </form>
    </div>
  );
}
