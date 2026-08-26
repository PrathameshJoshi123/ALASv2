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
1. **Template Fidelity Check**:
   - You MUST verify that the writer read all chunks sequentially. Ensure no sections or clauses from the template structure are missing, simplified, or omitted.
2. **Indian Law Correctness**:
   - You MUST ensure the contract is drafted strictly under **Indian Law** (and local state laws if a state is mentioned in the instructions).
   - Use `web_search` and `fetch_web_page` to check correctness, focusing on **Indian Kanoon** (`indiankanoon.org`) and **India Code** (`indiacode.nic.in`). Reject any foreign jurisdiction laws or formatting (e.g. US or UK conventions).
3. **Instruction Compliance**:
   - Verify that all custom requirements from the user's instructions (parties, financial terms, dates, governing law) are correctly and consistently integrated.
4. **Draft Quality**:
   - Check for left-behind placeholders, blanks (`___`), bracketed text, spelling, or numbering errors.
5. **Approval Decision**:
   - Explicitly output "APPROVED" if all checks pass, or "REJECTED" with a detailed checklist of corrections needed.
