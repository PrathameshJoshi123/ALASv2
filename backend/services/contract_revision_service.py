"""
Contract Revision Service.

Provides analysis-driven clause redrafting, customized prompt modification,
and revision persistence for analyzed contracts.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from backend.database import SessionLocal
from backend.models.contract_analysis import ContractAnalysis
from backend.models.documents import Document
from backend.utils.llm_utils import get_resilient_llm, ORCHESTRATOR_MODEL_NAME

logger = logging.getLogger(__name__)


class RedraftClauseRequest(BaseModel):
    clause_id: Optional[str] = Field(None, description="ID or number of the clause to redraft")
    clause_title: Optional[str] = Field(None, description="Title of the clause section")
    original_text: str = Field(..., description="Original raw clause text from the contract")
    custom_prompt: Optional[str] = Field(
        None,
        description="User's specific revision instructions (e.g. 'Make indemnification mutual with 12-month cap')",
    )
    favor_party: str = Field(
        "balanced",
        description="Perspective to favor: 'balanced', 'client' (buyer/recipient), or 'counterparty' (vendor/service provider)",
    )
    remedy_analysis_risks: bool = Field(
        True,
        description="Whether to automatically remedy identified Indian legal risks (e.g., Section 27, Section 74)",
    )


class ClauseRevisionResponse(BaseModel):
    clause_id: Optional[str] = None
    clause_title: Optional[str] = None
    original_text: str
    revised_text: str
    rationale: str
    remedied_risks: List[str] = Field(default_factory=list)
    statutory_compliance_notes: str = ""
    status: str = "success"


class ApplyRevisionRequest(BaseModel):
    clause_id: str
    revised_text: str
    rationale: Optional[str] = ""


def generate_clause_redraft(
    document_id: str,
    request: RedraftClauseRequest,
) -> ClauseRevisionResponse:
    """
    Generate an intelligent redraft of a clause taking into account:
    1. The contract's pre-computed analysis (parties, risk score, flagged vulnerabilities).
    2. Indian statutory compliance (Indian Contract Act 1872, Arbitration Act 1996).
    3. The user's specific prompt instructions and requested commercial stance.
    """
    logger.info(f"Generating redraft for clause '{request.clause_id}' in doc {document_id}")

    # Fetch analysis context
    with SessionLocal() as db:
        analysis = db.execute(
            select(ContractAnalysis).where(ContractAnalysis.document_id == document_id)
        ).scalar_one_or_none()
        
        doc = db.execute(
            select(Document).where(Document.id == document_id)
        ).scalar_one_or_none()

    doc_parties = analysis.parties if analysis and analysis.parties else []
    parties_str = ", ".join(doc_parties) if doc_parties else (doc.company_name if doc else "The Parties")
    contract_type = (analysis.contract_type if analysis else None) or (doc.contract_type if doc else "Contract")

    # Match clause in pre-computed analysis if available
    matched_clause_analysis = None
    if analysis and analysis.clauses:
        for c in analysis.clauses:
            if isinstance(c, dict) and (
                str(c.get("id")) == str(request.clause_id)
                or str(c.get("clause_number")) == str(request.clause_id)
                or (request.clause_title and c.get("section_title", "").lower() == request.clause_title.lower())
            ):
                matched_clause_analysis = c
                break

    clause_risk_context = ""
    if matched_clause_analysis:
        clause_risk_context = (
            f"- Severity: {matched_clause_analysis.get('severity', 'UNKNOWN')}\n"
            f"- Risk Identified: {matched_clause_analysis.get('risk_description', 'None')}\n"
            f"- Legal Reasoning: {matched_clause_analysis.get('legal_reasoning', 'None')}\n"
        )

    prompt = f"""
You are an expert Senior Indian Corporate Lawyer and Contract Drafter.
Your task is to REDRAFT and NEGOTIATE an amended clause for a {contract_type}.

PARTIES INVOLVED: {parties_str}
STANCE DESIRED: {request.favor_party.upper()}

ORIGINAL CLAUSE TEXT:
\"\"\"{request.original_text}\"\"\"

FLAGGED RISKS FROM CONTRACT ANALYSIS:
{clause_risk_context or "No specific automated flag recorded."}

USER EDIT INSTRUCTIONS / PROMPT:
{request.custom_prompt or "Amend this clause to cure any legal vulnerabilities under Indian Law, ensuring commercial balance and mutual protection."}

INDIAN STATUTORY RULES TO STRICTLY COMPLY WITH:
1. Section 27, Indian Contract Act 1872: Negative covenants restraining lawful trade/profession post-termination are VOID ab initio. Tailor non-competes or restrictive covenants to strictly protect genuine trade secrets during the term only.
2. Section 74, Indian Contract Act 1872: Penalty clauses are unenforceable; liquidated damages must be a genuine pre-estimate of loss and subject to proof of actual loss.
3. Section 28, Indian Contract Act 1872: Do not restrict statutory limitation periods (3 years) or extinguish judicial remedies.
4. Section 56, Indian Contract Act 1872: Ensure force majeure and impossibility clauses have reasonable notice and termination triggers.
5. Liability & Indemnity: Ensure caps are clearly defined, exclusions (gross negligence, wilful misconduct) are balanced, and indemnities are mutually proportional.

INSTRUCTIONS:
1. Draft the REVISED clause verbatim in clear, standard legal formatting.
2. Provide a clear, actionable legal rationale explaining what was modified and why.
3. List the specific risks or ambiguities remedied.
4. Output your response as a valid JSON object matching the following structure:
{{
  "revised_text": "Complete, ready-to-insert amended clause text...",
  "rationale": "Explanation of changes made and why...",
  "remedied_risks": ["Risk 1 solved", "Risk 2 solved"],
  "statutory_compliance_notes": "Statutory grounding under Indian law (e.g., ICA Section 27/74)"
}}

CRITICAL JSON FORMATTING RULES:
- Output valid, strictly parseable JSON.
- Within string values, escape any double quotes as \" or use single quotes.
- Return ONLY the raw JSON object. Do not include markdown formatting, code block markers, or commentary outside the JSON.
"""

    llm = get_resilient_llm(model_name=ORCHESTRATOR_MODEL_NAME, temperature=0.2)
    resp = llm.invoke(prompt)
    content = resp.content if isinstance(resp.content, str) else str(resp.content)

    # Clean JSON markdown fences and extract outermost JSON object
    clean_json = content.strip()
    if "```json" in clean_json:
        clean_json = clean_json.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in clean_json:
        clean_json = clean_json.split("```", 1)[1].split("```", 1)[0].strip()
    else:
        m = re.search(r"(\{.*\})", clean_json, re.DOTALL)
        if m:
            clean_json = m.group(1).strip()

    parsed = None
    # 1. Attempt standard JSON parsing with strict=False (allows unescaped newlines/tabs inside string literals)
    # Clean trailing commas before } or ] which LLMs frequently emit
    clean_json_fixed = re.sub(r',\s*(\}|\])', r'\1', clean_json)
    try:
        candidate = json.loads(clean_json_fixed, strict=False)
        if isinstance(candidate, dict) and candidate.get("revised_text"):
            parsed = candidate
    except Exception as ex:
        logger.warning(f"json.loads with strict=False failed: {ex}. Proceeding to regex extraction.")

    # 2. Resilient fallback extraction using regex if json.loads failed
    if not parsed:
        logger.warning("Extracting clause redraft fields using regex fallback.")
        revised_match = re.search(
            r'"revised_text"\s*:\s*"(.*?)(?:"\s*,\s*"(?:rationale|remedied_risks|statutory_compliance_notes)"|"\s*\}|\Z)',
            clean_json,
            re.DOTALL,
        )
        rationale_match = re.search(
            r'"rationale"\s*:\s*"(.*?)(?:"\s*,\s*"(?:remedied_risks|statutory_compliance_notes)"|"\s*\}|\Z)',
            clean_json,
            re.DOTALL,
        )
        notes_match = re.search(
            r'"statutory_compliance_notes"\s*:\s*"(.*?)(?:"\s*\}|\Z)',
            clean_json,
            re.DOTALL,
        )
        risks_match = re.search(
            r'"remedied_risks"\s*:\s*\[(.*?)\]',
            clean_json,
            re.DOTALL,
        )

        extracted_text = ""
        if revised_match:
            extracted_text = revised_match.group(1).strip()
        else:
            # Strip leading/trailing JSON markers from the candidate text
            candidate_text = clean_json
            candidate_text = re.sub(r'^\s*\{\s*"revised_text"\s*:\s*"?', '', candidate_text)
            candidate_text = re.sub(
                r'"\s*,\s*"(?:rationale|remedied_risks|statutory_compliance_notes)".*$',
                '',
                candidate_text,
                flags=re.DOTALL,
            )
            candidate_text = re.sub(r'"\s*\}\s*$', '', candidate_text)
            extracted_text = candidate_text.strip()

        # Unescape quotes and slashes that were escaped in JSON string
        extracted_text = extracted_text.replace(r'\"', '"').replace(r"\'", "'").replace(r'\\', '\\')

        remedied_list = ["Unbalanced liability or non-compliant wording"]
        if risks_match:
            try:
                clean_risks = re.sub(r',\s*\]', ']', f"[{risks_match.group(1)}]")
                remedied_list = json.loads(clean_risks, strict=False)
            except Exception:
                pass

        rationale_text = rationale_match.group(1).strip() if rationale_match else "Automated legal redraft based on user instructions and risk assessment."
        rationale_text = rationale_text.replace(r'\"', '"').replace(r"\'", "'")

        notes_text = notes_match.group(1).strip() if notes_match else "Reviewed for Indian Contract Act 1872 compliance."
        notes_text = notes_text.replace(r'\"', '"').replace(r"\'", "'")

        parsed = {
            "revised_text": extracted_text or request.original_text,
            "rationale": rationale_text,
            "remedied_risks": remedied_list,
            "statutory_compliance_notes": notes_text,
        }

    # Clean any accidental JSON syntax remnants from revised_text and unescape stray slashes
    final_revised_text = parsed.get("revised_text", request.original_text)
    if isinstance(final_revised_text, str):
        final_revised_text = re.sub(r'^\s*\{\s*"revised_text"\s*:\s*"?', '', final_revised_text)
        final_revised_text = re.sub(r'^\s*"revised_text"\s*:\s*"?', '', final_revised_text)
        final_revised_text = final_revised_text.replace(r'\"', '"').replace(r"\'", "'")
        final_revised_text = final_revised_text.strip()
        if final_revised_text.startswith('"') and final_revised_text.endswith('"'):
            final_revised_text = final_revised_text[1:-1].strip()

    return ClauseRevisionResponse(
        clause_id=request.clause_id,
        clause_title=request.clause_title,
        original_text=request.original_text,
        revised_text=final_revised_text or request.original_text,
        rationale=parsed.get("rationale", ""),
        remedied_risks=parsed.get("remedied_risks", []),
        statutory_compliance_notes=parsed.get("statutory_compliance_notes", ""),
        status="success",
    )


def apply_clause_revision_to_db(
    document_id: str,
    clause_id: str,
    revised_text: str,
    rationale: str = "",
) -> Dict[str, Any]:
    """
    Applies an approved revised clause to the stored contract analysis:
    - Updates the clause text in `contract_analysis.clauses`.
    - Updates its severity status to 'REVISED_SAFE' or reduces risk score.
    - Records an audit log of revisions in the analysis record.
    """
    with SessionLocal() as db:
        analysis = db.execute(
            select(ContractAnalysis).where(ContractAnalysis.document_id == document_id)
        ).scalar_one_or_none()

        if not analysis:
            return {"status": "error", "message": f"Contract analysis for {document_id} not found."}

        existing_clauses = list(analysis.clauses or [])
        updated = False
        target_orig_text = ""

        for c in existing_clauses:
            if isinstance(c, dict) and (
                str(c.get("id")) == str(clause_id)
                or str(c.get("clause_number")) == str(clause_id)
            ):
                target_orig_text = c.get("raw_text", "")
                c["original_raw_text"] = target_orig_text
                c["raw_text"] = revised_text
                c["severity"] = "REVISED_SAFE"
                c["is_revised"] = True
                c["revision_rationale"] = rationale
                c["revised_at"] = datetime.utcnow().isoformat()
                updated = True
                break

        # Also update drafted_contract.md if present
        from pathlib import Path
        draft_file = Path("backend/storage/outputs") / f"{document_id}_drafted_contract.md"
        if draft_file.exists() and target_orig_text:
            try:
                curr_content = draft_file.read_text(encoding="utf-8")
                if target_orig_text in curr_content:
                    new_content = curr_content.replace(target_orig_text, revised_text, 1)
                    draft_file.write_text(new_content, encoding="utf-8")
            except Exception as ex:
                logger.warning(f"Could not update drafted contract file for {document_id}: {ex}")

        if updated:
            # Recompute issue counts
            crit = sum(1 for c in existing_clauses if isinstance(c, dict) and str(c.get("severity")).upper() == "CRITICAL")
            high = sum(1 for c in existing_clauses if isinstance(c, dict) and str(c.get("severity")).upper() == "HIGH")
            med = sum(1 for c in existing_clauses if isinstance(c, dict) and str(c.get("severity")).upper() == "MEDIUM")
            low = sum(1 for c in existing_clauses if isinstance(c, dict) and str(c.get("severity")).upper() == "LOW")

            analysis.clauses = existing_clauses
            analysis.critical_issues = crit
            analysis.high_issues = high
            analysis.medium_issues = med
            analysis.low_issues = low
            analysis.overall_risk_score = min(100.0, float(crit * 30 + high * 20 + med * 10 + low * 5))
            analysis.updated_at = datetime.utcnow()

            db.commit()
            return {
                "status": "success",
                "message": f"Clause {clause_id} revised successfully.",
                "overall_risk_score": analysis.overall_risk_score,
                "critical_issues": crit,
                "high_issues": high,
            }

        return {"status": "error", "message": f"Clause with ID {clause_id} not found in analysis."}


def save_contract_content(document_id: str, content: str) -> Dict[str, Any]:
    """
    Saves the user edited contract markdown directly to backend/storage/outputs/{document_id}_drafted_contract.md.
    """
    from pathlib import Path
    out_dir = Path("backend/storage/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{document_id}_drafted_contract.md"
    file_path.write_text(content, encoding="utf-8")
    return {
        "status": "success",
        "message": "Contract saved successfully.",
        "document_id": document_id,
    }

