"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  PenTool,
  Paperclip,
  ArrowRight,
  FileText,
  Scale,
  Sparkles,
  Loader2,
  CheckCircle2,
  Sliders,
  ChevronDown,
  ChevronUp,
  X,
  ShieldCheck,
  Building2,
  Users,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface PrecedentBlueprint {
  id: string;
  title: string;
  contractType: string;
  favorParty: string;
  governingLaw: string;
  draftingStyle: string;
  companyName: string;
  counterpartyName: string;
  prompt: string;
  tags: string[];
}

const PRESET_BLUEPRINTS: PrecedentBlueprint[] = [
  {
    id: "saas-msa",
    title: "SaaS Master Subscription Agreement with 99.9% uptime SLA",
    contractType: "Master Services Agreement (MSA)",
    favorParty: "Client-Favored",
    governingLaw: "Indian Contract Act, 1872",
    draftingStyle: "Institutional Legal",
    companyName: "Acme Enterprises India Pvt. Ltd. (Client)",
    counterpartyName: "CloudScale Systems Private Limited (Vendor)",
    prompt:
      "Draft a comprehensive enterprise SaaS Master Subscription Agreement featuring a strict 99.9% uptime Service Level Agreement (SLA) with graduated service credit remedies. Include provisions for full client ownership of all uploaded data, strict DPDP Act / IT Act 2000 data privacy safeguards, reciprocal confidentiality, mutual indemnity for third-party IP infringement, and unilateral client termination for cause upon repeated SLA failure.",
    tags: ["99.9% SLA & Credits", "DPDP Compliant", "Client-Favored", "Mutual IP Indemnity"],
  },
  {
    id: "mutual-nda",
    title: "Mutual Non-Disclosure Agreement under Indian jurisdiction",
    contractType: "Non-Disclosure Agreement (NDA)",
    favorParty: "Balanced",
    governingLaw: "Indian Contract Act, 1872",
    draftingStyle: "Institutional Legal",
    companyName: "InnovateTech Solutions Pvt. Ltd.",
    counterpartyName: "Zenith Global Capital LLP",
    prompt:
      "Draft a bilateral mutual non-disclosure agreement protecting proprietary technical, financial, and strategic trade secrets exchanged during strategic partnership evaluations. Include a 3-year confidentiality survival period, return or certified destruction of confidential assets within 10 days of demand, standard commercial exclusions, and injunctive relief entitlement under Specific Relief Act 1963 without posting security.",
    tags: ["Reciprocal Protection", "3-Year Survival", "Specific Relief Act", "Balanced"],
  },
  {
    id: "commercial-lease",
    title: "Commercial Real Estate Lease with standard maintenance covenants",
    contractType: "Commercial Lease Agreement",
    favorParty: "Balanced",
    governingLaw: "Indian Contract Act, 1872",
    draftingStyle: "Institutional Legal",
    companyName: "Horizon Commercial Real Estate LLP (Lessor)",
    counterpartyName: "NextGen Software India Pvt. Ltd. (Lessee)",
    prompt:
      "Draft a commercial lease deed for Grade-A office premises in India. Include a 36-month lock-in period, 5% annual rent escalation, 6 months interest-free refundable security deposit returnable within 15 days of vacant possession, clear Common Area Maintenance (CAM) covenants, Lessor structural maintenance obligations, and Lessee right of quiet peaceful enjoyment.",
    tags: ["36-Mo Lock-in", "CAM Covenants", "Transfer of Property Act", "Balanced"],
  },
  {
    id: "consultant-ip",
    title: "Independent Consultant Agreement with IP assignment",
    contractType: "IP Assignment Agreement",
    favorParty: "Client-Favored",
    governingLaw: "Indian Contract Act, 1872",
    draftingStyle: "Institutional Legal",
    companyName: "Apex Digital Ventures Private Limited",
    counterpartyName: "Independent Specialist Consultant (Individual)",
    prompt:
      "Draft an independent contractor consulting agreement with comprehensive, irrevocable intellectual property assignment under Section 19 of Copyright Act 1957 (worldwide, perpetual, unconditional waiver of moral rights). Include milestone-based compensation schedule, 12-month post-termination non-solicitation of clients and employees, strict non-disclosure, and independent contractor classification indemnification.",
    tags: ["100% IP Assignment", "Sec 19 Copyright Act", "12-Mo Non-Solicit", "Client-Favored"],
  },
  {
    id: "employment-contract",
    title: "Employment Contract with Section 27 ICA compliant non-solicit",
    contractType: "Employment Contract",
    favorParty: "Balanced",
    governingLaw: "Indian Contract Act, 1872",
    draftingStyle: "Regulatory Strict",
    companyName: "Nexus Financial Technologies India Pvt. Ltd.",
    counterpartyName: "Appointed Executive Employee",
    prompt:
      "Draft an executive employment contract strictly compliant with Section 27 of the Indian Contract Act 1872. Feature enforceable 12-month post-employment non-solicitation of clients, prospects, and colleagues; non-compete covenants restricted strictly during active employment tenure; assignment of all inventions and proprietary developments; and a 90-day notice period or payment in lieu.",
    tags: ["Sec 27 ICA Compliant", "Work-for-Hire Inventions", "Non-Solicitation", "Regulatory Strict"],
  },
];

export default function DraftingStudioPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [prompt, setPrompt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [contractType, setContractType] = useState("Master Services Agreement (MSA)");
  const [favorParty, setFavorParty] = useState("Balanced");
  const [governingLaw, setGoverningLaw] = useState("Indian Contract Act, 1872");
  const [draftingStyle, setDraftingStyle] = useState("Institutional Legal");
  const [companyName, setCompanyName] = useState("");
  const [counterpartyName, setCounterpartyName] = useState("");
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [showPartiesConfig, setShowPartiesConfig] = useState(false);

  const [isGenerating, setIsGenerating] = useState(false);
  const [draftedContracts, setDraftedContracts] = useState<any[]>([]);
  const [loadingContracts, setLoadingContracts] = useState(true);

  useEffect(() => {
    async function loadContracts() {
      try {
        setLoadingContracts(true);
        const data = await apiClient.getContracts(1, 10);
        const items = data.items || (Array.isArray(data) ? data : []);
        setDraftedContracts(items);
      } catch (err) {
        console.error("Failed to load drafts:", err);
      } finally {
        setLoadingContracts(false);
      }
    }
    loadContracts();
  }, []);

  const handleSelectPreset = (preset: PrecedentBlueprint) => {
    setSelectedPresetId(preset.id);
    setPrompt(preset.prompt);
    setContractType(preset.contractType);
    setFavorParty(preset.favorParty);
    setGoverningLaw(preset.governingLaw);
    setDraftingStyle(preset.draftingStyle);
    setCompanyName(preset.companyName);
    setCounterpartyName(preset.counterpartyName);
    toast.success(`Preset loaded: ${preset.title.split(" with ")[0]}`);
  };

  const handleClearPreset = () => {
    setSelectedPresetId(null);
    setPrompt("");
    setCompanyName("");
    setCounterpartyName("");
  };

  const activePreset = PRESET_BLUEPRINTS.find((p) => p.id === selectedPresetId);

  const handleStartDrafting = async () => {
    if (!prompt.trim() && !file) {
      toast.error("Please enter contract instructions or attach a reference file");
      return;
    }

    setIsGenerating(true);
    const toastId = toast.loading("Configuring autonomous drafting pipeline with Kanoon orchestrator...");

    try {
      const optionsPayload = {
        contract_type: contractType,
        favor_party: favorParty,
        governing_law: governingLaw,
        drafting_style: draftingStyle,
        company_name: companyName.trim() || undefined,
        counterparty_name: counterpartyName.trim() || undefined,
      };

      if (file) {
        const res = await apiClient.uploadContract(file, {
          contract_prompt: prompt,
          contract_type: contractType,
          auto_analyze: false,
        });
        const docId = res.document_id || res.id;
        const draftRes = await apiClient.draftContract(
          docId,
          prompt || "Draft standard commercial contract based on provided template.",
          optionsPayload,
        );
        toast.success("Drafting pipeline initiated!", { id: toastId });
        router.push(
          `/dashboard/drafting/editor/${docId}?generating=true&drafting=true&prompt=${encodeURIComponent(
            prompt,
          )}&task_id=${draftRes.task_id}`,
        );
      } else {
        const draftRes = await apiClient.createDraftContract(
          prompt,
          contractType,
          optionsPayload,
        );
        const resolvedDocId = draftRes.document_id || draftRes.id || "draft";
        toast.success("Blueprint synthesized!", { id: toastId });
        router.push(
          `/dashboard/drafting/editor/${resolvedDocId}?generating=true&drafting=true&prompt=${encodeURIComponent(
            prompt,
          )}&task_id=${draftRes.task_id}`,
        );
      }
    } catch (err: any) {
      console.error("Drafting error", err);
      toast.error(err?.response?.data?.detail || "Failed to start drafting pipeline", {
        id: toastId,
      });
      setIsGenerating(false);
    }
  };

  return (
    <div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8">
      {/* 1. Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
            <span>Contract Drafting Studio</span> / <span>Blueprint Specifications</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Autonomous Agreement Synthesizer
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Synthesize legally enforceable, clause-by-clause commercial agreements with Indian Kanoon precedent integration.
          </p>
        </div>
      </div>

      {/* 2. Main Blueprint Generator */}
      <Card className="shadow-sm border-border">
        <CardHeader className="pb-3 border-b border-border/60">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <PenTool className="w-4 h-4 text-primary" />
              <CardTitle className="text-sm font-semibold">
                Contract Blueprint Specifications
              </CardTitle>
            </div>
            <div className="flex items-center gap-2">
              {activePreset && (
                <Badge variant="outline" className="text-[10px] bg-accent/10 text-accent border-accent/30 font-medium">
                  Active Preset: {activePreset.contractType}
                </Badge>
              )}
              <Badge variant="outline" className="text-[10px]">
                Kanoon & ICA Orchestrator V2.4
              </Badge>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-4 pt-4">
          <textarea
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              if (selectedPresetId) setSelectedPresetId(null);
            }}
            rows={4}
            placeholder="Specify contract details, parties, key terms, liability caps, and jurisdiction (e.g. 'Software development agreement between ABC Tech and XYZ Retail, with 100% IP assignment, 12-month non-solicit, and arbitration in Mumbai under ICA')."
            className="w-full rounded-md border border-input bg-background p-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring leading-relaxed resize-none"
          />

          {/* Quick Preset Buttons */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-muted-foreground">
                Precedent Blueprints:
              </p>
              {selectedPresetId && (
                <button
                  type="button"
                  onClick={handleClearPreset}
                  className="text-[11px] text-muted-foreground hover:text-foreground flex items-center gap-1 underline underline-offset-2"
                >
                  <X className="w-3 h-3" />
                  Reset to Custom
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {PRESET_BLUEPRINTS.map((bp) => {
                const isSelected = selectedPresetId === bp.id;
                return (
                  <button
                    key={bp.id}
                    type="button"
                    onClick={() => handleSelectPreset(bp)}
                    className={`text-xs px-2.5 py-1.5 rounded border transition-colors text-left flex items-center gap-1.5 ${
                      isSelected
                        ? "border-primary bg-primary text-primary-foreground font-semibold shadow-xs"
                        : "border-border bg-muted/40 hover:bg-muted text-foreground"
                    }`}
                  >
                    <span>{bp.title}</span>
                  </button>
                );
              })}
            </div>

            {/* Active Preset Metadata Pills */}
            {activePreset && (
              <div className="flex items-center gap-2 pt-1">
                <span className="text-[11px] text-muted-foreground">Preset Focus:</span>
                <div className="flex flex-wrap gap-1.5">
                  {activePreset.tags.map((tag, idx) => (
                    <span
                      key={idx}
                      className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 font-medium"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Drafting Parameters Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-3 border-t border-border">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-foreground">
                Agreement Type
              </label>
              <select
                value={contractType}
                onChange={(e) => setContractType(e.target.value)}
                className="w-full h-8 px-2.5 rounded border border-input bg-background text-xs text-foreground focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="Master Services Agreement (MSA)">Master Services Agreement (MSA)</option>
                <option value="Non-Disclosure Agreement (NDA)">Non-Disclosure Agreement (NDA)</option>
                <option value="Commercial Lease Agreement">Commercial Lease Agreement</option>
                <option value="Employment Contract">Employment Contract</option>
                <option value="IP Assignment Agreement">IP Assignment Agreement</option>
                <option value="Vendor / Procurement Agreement">Vendor / Procurement Agreement</option>
                <option value="Independent Consultant Agreement">Independent Consultant Agreement</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-foreground">
                Posture & Favoring Party
              </label>
              <select
                value={favorParty}
                onChange={(e) => setFavorParty(e.target.value)}
                className="w-full h-8 px-2.5 rounded border border-input bg-background text-xs text-foreground focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="Balanced">Balanced / Mutual</option>
                <option value="Client-Favored">Client-Favored (Aggressive)</option>
                <option value="Counterparty-Favored">Counterparty-Favored</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-foreground">
                Governing Jurisdiction
              </label>
              <select
                value={governingLaw}
                onChange={(e) => setGoverningLaw(e.target.value)}
                className="w-full h-8 px-2.5 rounded border border-input bg-background text-xs text-foreground focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="Indian Contract Act, 1872">Indian Contract Act, 1872 (Pan-India)</option>
                <option value="Arbitration & Conciliation Act, 1996">Arbitration & Conciliation Act, 1996</option>
                <option value="Companies Act, 2013 Compliance">Companies Act, 2013 Compliance</option>
                <option value="IT Act 2000 & DPDP Standard">IT Act 2000 & DPDP Standard</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-foreground">
                Drafting Style & Tone
              </label>
              <select
                value={draftingStyle}
                onChange={(e) => setDraftingStyle(e.target.value)}
                className="w-full h-8 px-2.5 rounded border border-input bg-background text-xs text-foreground focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="Institutional Legal">Institutional Legal (Tier-1 Standard)</option>
                <option value="Plain English Commercial">Plain English Commercial</option>
                <option value="Regulatory Strict">Regulatory Strict & Compliance-Heavy</option>
              </select>
            </div>
          </div>

          {/* Contracting Parties Settings */}
          <div className="pt-2 border-t border-border">
            <button
              type="button"
              onClick={() => setShowPartiesConfig(!showPartiesConfig)}
              className="flex items-center justify-between w-full text-xs font-semibold text-muted-foreground hover:text-foreground py-1 transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5" />
                <span>Designate Contracting Parties (Optional)</span>
                {(companyName || counterpartyName) && (
                  <Badge variant="outline" className="text-[10px] ml-1">Configured</Badge>
                )}
              </div>
              {showPartiesConfig ? (
                <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              )}
            </button>

            {showPartiesConfig && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2.5 pb-1">
                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-foreground flex items-center gap-1">
                    <Building2 className="w-3 h-3 text-muted-foreground" />
                    First Party / Client Name
                  </label>
                  <Input
                    type="text"
                    placeholder="e.g. Acme Corp Pvt. Ltd. (Client / Employer)"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-foreground flex items-center gap-1">
                    <Users className="w-3 h-3 text-muted-foreground" />
                    Second Party / Counterparty Name
                  </label>
                  <Input
                    type="text"
                    placeholder="e.g. Zenith Global Ltd. (Vendor / Consultant / Employee)"
                    value={counterpartyName}
                    onChange={(e) => setCounterpartyName(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Action Row */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-border">
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setFile(e.target.files[0]);
                }
              }}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              className="text-xs w-full sm:w-auto"
            >
              <Paperclip className="w-3.5 h-3.5 mr-1.5" />
              {file ? file.name : "Attach Reference Document (Optional)"}
            </Button>

            <Button
              type="button"
              variant="default"
              size="sm"
              loading={isGenerating}
              disabled={isGenerating || (!prompt.trim() && !file)}
              onClick={handleStartDrafting}
              className="text-xs w-full sm:w-auto font-medium"
            >
              <span>Launch Autonomous Drafting</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 3. Recent Drafts & Repository */}
      <Card className="shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold">
            Drafting History & Saved Documents
          </CardTitle>
          <CardDescription className="text-xs">
            Open previously generated contracts in the interactive redline editor
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loadingContracts ? (
            <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Loading drafting records...</span>
            </div>
          ) : draftedContracts.length === 0 ? (
            <div className="p-8 text-center text-xs text-muted-foreground">
              No contracts drafted yet. Fill out the blueprint above to synthesize an agreement.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Document Title</TableHead>
                  <TableHead className="text-xs">Type</TableHead>
                  <TableHead className="text-xs">Counterparty</TableHead>
                  <TableHead className="text-xs">Date</TableHead>
                  <TableHead className="text-xs text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {draftedContracts.map((c) => (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer hover:bg-muted/40 transition-colors"
                    onClick={() => router.push(`/dashboard/drafting/editor/${c.id}`)}
                  >
                    <TableCell className="font-semibold text-xs text-foreground py-3">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-muted-foreground" />
                        <span className="truncate max-w-[240px]">
                          {c.original_filename || c.markdown_file || "Custom Contract Draft"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground py-3">
                      {c.contract_type || "Commercial"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground py-3">
                      {c.counterparty_name || "Unspecified"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground py-3">
                      {c.created_at ? new Date(c.created_at).toLocaleDateString() : "Recent"}
                    </TableCell>
                    <TableCell className="text-xs text-right py-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push(`/dashboard/drafting/editor/${c.id}`);
                        }}
                        className="text-xs h-7 px-2 font-semibold text-accent hover:underline"
                      >
                        Open Editor
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
