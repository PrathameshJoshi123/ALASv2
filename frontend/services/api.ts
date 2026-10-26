import axios, { AxiosInstance } from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AnalysisPayload = {
  overall_risk_score: number;
  critical_issues: number;
  high_issues: number;
  medium_issues: number;
  low_issues: number;
  analysis_summary: string;
  recommended_actions: string[];
  key_findings: string[];
  unresolved_questions: string[];
  obligations: any[];
  risks: any[];
  legal_sources?: any[];
  clauses: any[];
  analysis_markdown?: string;
  source?: string;
  status?: string;
  live?: Record<string, any>;
  detailed_suggestions?: any;
};

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  // Contract endpoints
  async uploadContract(
    file: File,
    metadata: {
      company_name?: string;
      counterparty_name?: string;
      contract_type?: string;
      contract_prompt?: string;
      auto_analyze?: boolean;
    },
  ) {
    const formData = new FormData();
    formData.append("file", file);
    if (metadata.company_name) formData.append("company_name", metadata.company_name);
    if (metadata.counterparty_name) formData.append("counterparty_name", metadata.counterparty_name);
    if (metadata.contract_type) formData.append("contract_type", metadata.contract_type);
    if (metadata.contract_prompt) formData.append("contract_prompt", metadata.contract_prompt);
    if (metadata.auto_analyze !== undefined) formData.append("auto_analyze", String(metadata.auto_analyze));

    const response = await this.client.post("/api/v1/contracts/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });

    return response.data;
  }

  async getContracts(page = 1, limit = 10) {
    const response = await this.client.get("/api/v1/contracts/", {
      params: { page, page_size: limit },
    });
    const data = response.data;
    if (Array.isArray(data)) {
      return {
        items: data,
        total: data.length,
      };
    }
    return data;
  }

  async getContractDetails(contractId: string) {
    const response = await this.client.get(`/api/v1/contracts/${contractId}`);
    return response.data;
  }

  async getContractClauses(contractId: string) {
    const analysis = await this.getContractAnalysis(contractId);
    return { items: analysis.clauses || [] };
  }

  private normalizeAnalysisPayload(raw: any): AnalysisPayload {
    const data = raw?.analysis || raw || {};
    const base: AnalysisPayload = {
      overall_risk_score: Number(
        data?.overall_risk_score || raw?.overall_risk_score || data?.risk_score || 0,
      ),
      critical_issues: Number(data?.critical_issues || raw?.critical_issues || data?.critical || 0),
      high_issues: Number(data?.high_issues || raw?.high_issues || data?.high || 0),
      medium_issues: Number(data?.medium_issues || raw?.medium_issues || data?.medium || 0),
      low_issues: Number(data?.low_issues || raw?.low_issues || data?.low || 0),
      analysis_summary:
        data?.analysis_summary || raw?.analysis_summary || data?.summary || raw?.summary || "Analysis in progress...",
      recommended_actions: Array.isArray(data?.recommended_actions)
        ? data.recommended_actions
        : Array.isArray(raw?.recommended_actions)
          ? raw.recommended_actions
          : [],
      key_findings: Array.isArray(data?.key_findings)
        ? data.key_findings
        : Array.isArray(raw?.key_findings)
          ? raw.key_findings
          : [],
      unresolved_questions: Array.isArray(data?.unresolved_questions)
        ? data.unresolved_questions
        : Array.isArray(raw?.unresolved_questions)
          ? raw.unresolved_questions
          : [],
      obligations: Array.isArray(data?.obligations)
        ? data.obligations
        : Array.isArray(raw?.obligations)
          ? raw.obligations
          : [],
      risks: Array.isArray(data?.risks)
        ? data.risks
        : Array.isArray(raw?.risks)
          ? raw.risks
          : [],
      legal_sources: Array.isArray(data?.legal_sources)
        ? data.legal_sources
        : Array.isArray(raw?.legal_sources)
          ? raw.legal_sources
          : [],
      clauses: [],
      analysis_markdown:
        raw?.analysis_markdown ||
        raw?.analysis?.analysis_markdown ||
        data?.analysis_markdown ||
        data?.analysis?.analysis_markdown ||
        "",
      source: raw?.source,
      status: raw?.status,
      live: raw?.live,
      detailed_suggestions: raw?.detailed_suggestions,
    };

    const rawClauses = data?.clauses || raw?.clauses;
    if (Array.isArray(rawClauses)) {
      base.clauses = rawClauses.map((c: any, i: number) => ({
        id: c?.id || c?.clause_id || `${i + 1}`,
        clause_number: c?.clause_number || i + 1,
        clause_type: c?.clause_type || c?.type || "general",
        section_title: c?.section_title || c?.title || `Clause ${i + 1}`,
        raw_text: c?.raw_text || c?.text || "",
        severity: String(c?.severity || "info").toUpperCase(),
        risk_description: c?.risk_description || c?.risk || "",
        legal_reasoning: c?.legal_reasoning || c?.reasoning || "",
        confidence_score: Number(c?.confidence_score || c?.confidence || 0),
        applicable_statute: c?.applicable_statute,
        statute_section: c?.statute_section,
      }));
    }

    return base;
  }

  async getContractAnalysis(contractId: string) {
    try {
      const response = await this.client.get(
        `/api/v1/contracts/${contractId}`,
      );
      return this.normalizeAnalysisPayload(
        response.data || {},
      );
    } catch {
      return this.normalizeAnalysisPayload({});
    }
  }

  async deleteContract(contractId: string) {
    const response = await this.client.delete(`/api/v1/contracts/${contractId}`);
    return response.data;
  }

  async analyzeContract(contractId: string) {
    const response = await this.client.post(
      `/api/v1/contracts/${contractId}/analyze`,
    );
    return response.data;
  }

  async getContractLogs(contractId: string) {
    const response = await this.client.get(
      `/api/v1/contracts/${contractId}/logs`,
    );
    return response.data;
  }


  async processContract(contractId: string) {
    const response = await this.client.post(
      `/api/v1/contracts/${contractId}/process`,
    );
    return response.data;
  }

  async getProcessingStatus(documentId: string, taskId: string) {
    const response = await this.client.get(
      `/api/v1/contracts/${documentId}/process/status/${taskId}`,
    );
    return response.data;
  }

  async askContractQuestion(contractId: string, question: string) {
    const response = await this.client.post(
      `/api/v1/contracts/${contractId}/qa`,
      { question },
    );
    return response.data;
  }

  async getContractQAHistory(contractId: string) {
    const response = await this.client.get(
      `/api/v1/contracts/${contractId}/qa/history`,
    );
    return response.data;
  }

  async clearContractQAHistory(contractId: string) {
    const response = await this.client.delete(
      `/api/v1/contracts/${contractId}/qa/history`,
    );
    return response.data;
  }

  async redraftClause(contractId: string, payload: {
    clause_id?: string;
    clause_title?: string;
    original_text: string;
    custom_prompt?: string;
    favor_party?: string;
  }) {
    const response = await this.client.post(
      `/api/v1/contracts/${contractId}/redraft-clause`,
      payload,
    );
    return response.data;
  }

  async applyClauseRevision(contractId: string, payload: {
    clause_id: string;
    revised_text: string;
    rationale?: string;
  }) {
    const response = await this.client.post(
      `/api/v1/contracts/${contractId}/apply-revision`,
      payload,
    );
    return response.data;
  }

  async saveContractContent(contractId: string, content: string) {
    const response = await this.client.post(
      `/api/v1/contracts/${contractId}/save-content`,
      { content },
    );
    return response.data;
  }




  // Contract drafting endpoints
  async createDraftContract(
    prompt: string,
    contractType = "Custom Contract",
    options?: {
      favor_party?: string;
      governing_law?: string;
      drafting_style?: string;
      company_name?: string;
      counterparty_name?: string;
    },
  ) {
    const response = await this.client.post("/api/v1/contracts/draft/create", {
      contract_prompt: prompt,
      contract_type: contractType,
      favor_party: options?.favor_party || "Balanced",
      governing_law: options?.governing_law || "Indian Contract Act, 1872",
      drafting_style: options?.drafting_style || "Institutional Legal",
      company_name: options?.company_name || null,
      counterparty_name: options?.counterparty_name || null,
    });
    return response.data;
  }

  async draftContract(
    documentId: string,
    draftingInstructions: string,
    options?: {
      contract_type?: string;
      favor_party?: string;
      governing_law?: string;
      drafting_style?: string;
      company_name?: string;
      counterparty_name?: string;
    },
  ) {
    const response = await this.client.post(
      `/api/v1/contracts/${documentId}/draft`,
      {
        drafting_instructions: draftingInstructions,
        contract_type: options?.contract_type,
        favor_party: options?.favor_party || "Balanced",
        governing_law: options?.governing_law || "Indian Contract Act, 1872",
        drafting_style: options?.drafting_style || "Institutional Legal",
        company_name: options?.company_name || null,
        counterparty_name: options?.counterparty_name || null,
      },
    );
    return response.data;
  }

  async reiterateContract(documentId: string, instructions: string) {
    const response = await this.client.post(
      `/api/v1/contracts/${documentId}/reiterate`,
      { instructions },
    );
    return response.data;
  }

  async getDraftEvents(documentId: string) {
    const response = await this.client.get(
      `/api/v1/contracts/${documentId}/draft/events`,
    );
    return response.data;
  }

  async getDraftLogs(documentId: string) {
    const response = await this.client.get(
      `/api/v1/contracts/${documentId}/draft/logs`,
    );
    return response.data;
  }

  async getContractDraftVersions(documentId: string) {
    const response = await this.client.get(
      `/api/v1/contracts/${documentId}/draft/versions`,
    );
    return response.data;
  }

  getDraftStreamUrl(documentId: string) {
    return `${API_URL}/api/v1/contracts/${documentId}/draft/stream`;
  }


  // Case File Analysis endpoints
  async getCases() {
    const response = await this.client.get("/api/v1/cases");
    return response.data;
  }

  async getCaseDetails(caseId: string) {
    const response = await this.client.get(`/api/v1/cases/${caseId}`);
    return response.data;
  }

  async createCase(data: { title: string; description?: string }) {
    const response = await this.client.post("/api/v1/cases", data);
    return response.data;
  }

  async uploadCaseDocument(caseId: string, file: File) {
    const formData = new FormData();
    formData.append("file", file);
    const response = await this.client.post(`/api/v1/cases/${caseId}/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  }

  async triggerCaseAnalysis(caseId: string) {
    const response = await this.client.post(`/api/v1/cases/${caseId}/analyze`);
    return response.data;
  }

  async getCaseAnalysis(caseId: string) {
    const response = await this.client.get(`/api/v1/cases/${caseId}/analysis`);
    return response.data;
  }

  async getCaseTimeline(caseId: string) {
    const response = await this.client.get(`/api/v1/cases/${caseId}/timeline`);
    return response.data;
  }

  async askCaseQuestion(caseId: string, question: string) {
    const response = await this.client.post(`/api/v1/cases/${caseId}/qa`, { question });
    return response.data;
  }

  async getCaseLogs(caseId: string) {
    const response = await this.client.get(`/api/v1/cases/${caseId}/logs`);
    return response.data;
  }
}

export const apiClient = new APIClient();

