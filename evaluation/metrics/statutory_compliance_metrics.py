"""
Statutory Compliance and Redline Verification Metrics.

Evaluates adherence to Indian statutory and precedent standards:
- Section 27 ICA 1872 (Restraint of Trade / Non-Compete remediation rate)
- Section 74 ICA 1872 (Liquidated Damages / Penalty capping rate)
- Section 28 ICA 1872 (Agreements in Restraint of Legal Proceedings)
- Perkins Eastman Doctrine (Unilateral Sole Arbitrator neutralization)
- Indian Kanoon Citation Authenticity Rate
"""

from typing import Any, Dict, List, Optional
import re


def evaluate_statutory_remediation(
    original_clause: str,
    redrafted_clause: str,
    statute_type: str
) -> Dict[str, Any]:
    """
    Verify whether the redrafted clause has successfully cured the statutory defect.
    """
    orig_lower = original_clause.lower()
    redraft_lower = redrafted_clause.lower()

    remedy_success = False
    details = ""

    if statute_type == "SECTION_27_NON_COMPETE":
        # Sec 27 ICA voids post-termination non-compete in India
        has_post_term_ban = any(k in orig_lower for k in ["after termination", "post-employment", "following termination", "shall not engage"])
        cured_post_term = (
            "during the term" in redraft_lower or
            "during employment" in redraft_lower or
            "non-disclosure" in redraft_lower or
            "confidentiality" in redraft_lower or
            "without imposing any post-termination restraint" in redraft_lower
        )
        has_retained_void_ban = "for a period of" in redraft_lower and "after termination" in redraft_lower
        remedy_success = cured_post_term and not has_retained_void_ban
        details = "Remedied post-employment non-compete to enforceable during-term covenant" if remedy_success else "Retained void post-termination non-compete"

    elif statute_type == "SECTION_74_LIQUIDATED_DAMAGES":
        # Sec 74 ICA caps damages to reasonable compensation; prohibits punitive penalties
        has_punitive = any(k in orig_lower for k in ["penalty", "forfeit all", "100%", "without proof of loss"])
        cured = (
            "reasonable compensation" in redraft_lower or
            "genuine pre-estimate" in redraft_lower or
            "subject to proof of actual loss" in redraft_lower or
            "capped at" in redraft_lower
        )
        remedy_success = cured
        details = "Replaced punitive penalty with genuine pre-estimate / reasonable compensation cap" if remedy_success else "Did not add reasonable compensation cap"

    elif statute_type == "PERKINS_EASTMAN_ARBITRATION":
        # Unilateral appointment of sole arbitrator is void
        has_unilateral = any(k in orig_lower for k in ["sole discretion of company", "appointed solely by", "unilaterally appoint"])
        cured = (
            "mutual agreement" in redraft_lower or
            "institutional arbitration" in redraft_lower or
            "diac" in redraft_lower or
            "mcia" in redraft_lower or
            "presiding arbitrator" in redraft_lower
        )
        remedy_success = cured
        details = "Substituted unilateral sole arbitrator with mutual/institutional appointment" if remedy_success else "Unilateral arbitrator persists"

    else:
        # Generic statutory compliance check
        remedy_success = len(redraft_lower) > 20 and redraft_lower != orig_lower
        details = "Custom revision applied"

    return {
        "statute_type": statute_type,
        "remedy_success": remedy_success,
        "details": details,
        "length_change": len(redrafted_clause) - len(original_clause),
    }


def compute_kanoon_citation_authenticity(citations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Measure the authenticity of Indian Kanoon citations returned by the autonomous research loop.
    Checks for genuine numeric doc IDs and valid indiankanoon.org URLs.
    """
    if not citations:
        return {"total_citations": 0, "valid_citations": 0, "authenticity_rate": 1.0}

    valid_count = 0
    for cite in citations:
        doc_id = str(cite.get("doc_id", "")).strip()
        url = str(cite.get("url", "")).strip()
        
        has_valid_id = bool(re.match(r"^\d{4,9}$", doc_id))
        has_valid_url = "indiankanoon.org" in url and any(p in url for p in ["/doc/", "/docfragment/"])
        
        if has_valid_id or has_valid_url:
            valid_count += 1

    rate = valid_count / len(citations) if len(citations) > 0 else 1.0
    return {
        "total_citations": len(citations),
        "valid_citations": valid_count,
        "authenticity_rate": round(rate, 3)
    }

