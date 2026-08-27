---
name: contract-drafting-review
description: >
  Review the drafted contract against user instructions
  and template structures to ensure completeness, correctness,
  and overall quality.
---

# Contract Review Skill

## Role
Conduct a rigorous audit of the drafted Markdown contract to ensure compliance with the original template, user requirements, and legal correctness under Indian law.

## Review Checklist
1. **Template Fidelity & Ground Truth Check**:
   - Verify that the writer read all template chunks sequentially. The original template structure, user prompt, and research notes are your sole ground truth.
2. **Indian Law Correctness**:
   - Verify the contract complies strictly with **Indian Law**. Stick strictly and exclusively to **Indian Kanoon** (`indiankanoon.org`) for all legal checks (including the Indian Contract Act, 1872). Do NOT use or search India Code (`indiacode.nic.in`). Reject any foreign laws or terms.
3. **Instruction Compliance & Requirements Traceability**:
   - Compare the drafted contract against the user's original instructions to ensure no requirements have disappeared or been distorted (e.g. if instructions say "either party can terminate during probation," ensure both have that right in the draft).
4. **Usage & Consistency Check (Unused Definitions)**:
   - For every defined term in the contract, audit its usage. If a term is defined but used 0 times (e.g. Affiliate, Person, or corporate definitions copied by template contamination), flag it for removal.
5. **Issue Categorization**:
   Classify all found discrepancies, gaps, or issues into the following four categories:
   - **CRITICAL / HIGH (Legal Review Triggers - FLAG, DO NOT AUTO-CORRECT)**:
     - Post-employment restraints (e.g. 2-year non-compete under Sec 27 of Indian Contract Act, 1872; non-solicitation).
     - Broad immediate termination causes (e.g. termination for a criminal *charge* vs *conviction*, or extremely broad moral turpitude behavioral terms).
     - Overbroad IP assignment clauses lacking standard exclusions (e.g. background IP, open-source contributions, non-work resources).
     - Overbroad confidentiality clauses lacking exceptions (public domain, independent development, legal disclosure).
     *Note: You must FLAG these issues with risk descriptions and authorities, but DO NOT modify or silently delete them. Human review/confirmation is required.*
   - **MEDIUM (Drafting/Requirements Discrepancies)**:
     - Mismatches against user instructions (e.g., notice period rights missing for one party, fabricated CTC structure/components when user only provided lump-sum CTC).
     - Internal drafting conflicts (e.g. exclusive court jurisdiction vs arbitration clause venue discrepancies).
   - **LOW / CLEANUP (Template Contamination)**:
     - Unused defined terms, formatting inconsistencies, or redundant clauses.
   - **MISSING (Information Gaps)**:
     - Blanks, residential/registered addresses, signatory names, or designations. Indicate as `STATUS = INCOMPLETE` / `SEVERITY = INFORMATION REQUIRED` instead of an error.

6. **Approval Decision**:
   - Explicitly output "APPROVED" if all checks pass, or "REJECTED" with the structured checklist of corrections categorizing each item clearly as CRITICAL/HIGH, MEDIUM, LOW, or MISSING. Never invent/fabricate missing values or case laws.
