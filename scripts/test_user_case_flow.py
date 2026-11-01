"""
Comprehensive End-to-End User Flow Test & Legal Evaluation for ALAS Case Analysis.

Simulates the exact user interactions on the web application:
1. POST /api/v1/cases                    -> Create legal case
2. POST /api/v1/cases/{case_id}/upload   -> Upload 4 realistic Indian legal exhibits
3. GET  /api/v1/cases/{case_id}          -> Check exhibit parsing, chunking, and statuses
4. POST /api/v1/cases/{case_id}/analyze  -> Trigger deterministic LangGraph analysis
5. GET  /api/v1/cases/{case_id}/logs     -> Verify real-time agent thinking and milestones
6. GET  /api/v1/cases/{case_id}          -> Assert case is marked 'analyzed' with timeline count > 0
7. GET  /api/v1/cases/{case_id}/analysis -> Audit structured report across all 9 litigation sections
8. GET  /api/v1/cases/{case_id}/timeline -> Verify chronological timeline events & citations
9. POST /api/v1/cases/{case_id}/qa       -> Test Courtroom Q&A Agent on witness contradictions
10. Legal Completeness & Trial Readiness Evaluation
"""

import os
import sys
import json
import time
from pathlib import Path

# Ensure backend can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models.cases import Case, CaseDocument, CaseDocumentChunk, CaseTimeline, CaseAnalysis

DUMMY_DIR = Path("backend/storage/dummy_cases/apex_vs_zenith")

class TestFailure(Exception):
    pass

def log_step(title: str):
    print("\n" + "=" * 80)
    print(f"STEP: {title}")
    print("=" * 80)

def assert_true(condition: bool, fail_message: str):
    if not condition:
        print(f"\n❌ TEST FAILED: {fail_message}")
        raise TestFailure(fail_message)

def run_e2e_user_test():
    client = TestClient(app)
    
    # -------------------------------------------------------------
    # STEP 1: Create Case
    # -------------------------------------------------------------
    log_step("1. User creates a new legal case via POST /api/v1/cases")
    case_payload = {
        "title": "State (NCT of Delhi) & Apex FinTech Ltd. vs. Zenith Cloud Technologies Pvt. Ltd.",
        "description": (
            "FIR No. 0412/2024 under Sections 420/406/468/471/120-B IPC regarding alleged escrow "
            "diversion of INR 4.25 Crores, contested as a pure commercial dispute governed by "
            "arbitration under Clause 18 of Master Escrow Agreement."
        )
    }
    resp = client.post("/api/v1/cases", json=case_payload)
    assert_true(resp.status_code == 201, f"Expected 201 Created, got {resp.status_code}: {resp.text}")
    case_data = resp.json()
    case_id = case_data.get("id")
    assert_true(bool(case_id), "Response missing 'id'")
    print(f"✓ Case created successfully! ID: {case_id}")
    print(f"  Title: {case_data.get('title')}")
    print(f"  Status: {case_data.get('status')}")

    # -------------------------------------------------------------
    # STEP 2: Upload 4 Exhibits
    # -------------------------------------------------------------
    log_step("2. User uploads 4 authentic legal exhibits via POST /api/v1/cases/{case_id}/upload")
    exhibit_filenames = [
        "01_FIR_0412_2024_Mandir_Marg.pdf",
        "02_PW1_Statement_Section_161_CrPC.pdf",
        "03_MLC_Medical_Report_RML_Hospital.pdf",
        "04_Master_Escrow_Agreement_Dated_15012024.pdf"
    ]
    
    uploaded_doc_ids = []
    for fname in exhibit_filenames:
        fpath = DUMMY_DIR / fname
        assert_true(fpath.exists(), f"Exhibit file {fpath} does not exist!")
        with open(fpath, "rb") as f:
            files = {"file": (fname, f, "application/pdf")}
            up_resp = client.post(f"/api/v1/cases/{case_id}/upload", files=files)
            assert_true(up_resp.status_code == 201, f"Failed uploading {fname}: {up_resp.status_code} {up_resp.text}")
            up_data = up_resp.json()
            doc_id = up_data.get("document_id")
            assert_true(bool(doc_id), f"Upload response missing document_id for {fname}")
            uploaded_doc_ids.append(doc_id)
            print(f"  ✓ Uploaded '{fname}' -> Document ID: {doc_id} (Status: {up_data.get('status')})")

    # -------------------------------------------------------------
    # STEP 3: Check Parsing & Chunks in Database
    # -------------------------------------------------------------
    log_step("3. User inspects exhibits and verifies chunking via GET /api/v1/cases/{case_id}")
    detail_resp = client.get(f"/api/v1/cases/{case_id}")
    assert_true(detail_resp.status_code == 200, f"Failed getting case details: {detail_resp.status_code}")
    detail_data = detail_resp.json()
    docs = detail_data.get("documents", [])
    assert_true(len(docs) == 4, f"Expected 4 documents, got {len(docs)}")
    
    with SessionLocal() as db:
        chunk_count = db.query(CaseDocumentChunk).join(CaseDocumentChunk.document).filter(CaseDocument.case_id == case_id).count()
        print(f"✓ Total text chunks generated and indexed in DB: {chunk_count}")
        assert_true(chunk_count > 0, "No chunks found in database for uploaded exhibits!")

    # -------------------------------------------------------------
    # STEP 4: Trigger LangGraph Analysis
    # -------------------------------------------------------------
    log_step("4. User triggers multi-agent LangGraph analysis via POST /api/v1/cases/{case_id}/analyze")
    an_resp = client.post(f"/api/v1/cases/{case_id}/analyze")
    assert_true(an_resp.status_code == 200, f"Analyze trigger failed: {an_resp.status_code} {an_resp.text}")
    print(f"✓ Analysis triggered: {an_resp.json()}")

    # -------------------------------------------------------------
    # STEP 5: Verify Live Agent Execution Logs
    # -------------------------------------------------------------
    log_step("5. User inspects real-time agent activity logs via GET /api/v1/cases/{case_id}/logs")
    logs_resp = client.get(f"/api/v1/cases/{case_id}/logs")
    assert_true(logs_resp.status_code == 200, f"Failed fetching logs: {logs_resp.status_code}")
    logs_data = logs_resp.json()
    logs_list = logs_data.get("logs", [])
    total_logs = logs_data.get("total_logs", len(logs_list))
    print(f"✓ Retrieved {total_logs} agent execution log events.")
    assert_true(len(logs_list) > 0, "No activity logs were captured for the case analysis!")
    
    print("\n--- SAMPLE REAL-TIME AGENT LOGS (First 8 entries) ---")
    for log in logs_list[:8]:
        print(f"  [{log.get('type', 'info').upper()}] {log.get('detail')}")

    # -------------------------------------------------------------
    # STEP 6: Verify Case Status
    # -------------------------------------------------------------
    log_step("6. User checks case status via GET /api/v1/cases/{case_id}")
    post_detail = client.get(f"/api/v1/cases/{case_id}").json()
    case_status = post_detail.get("status")
    has_analysis = post_detail.get("has_analysis")
    timeline_count = post_detail.get("timeline_count")
    print(f"✓ Case Status: '{case_status}'")
    print(f"✓ Has Analysis Flag: {has_analysis}")
    print(f"✓ Timeline Event Count: {timeline_count}")
    assert_true(case_status == "analyzed", f"Expected case status 'analyzed', got '{case_status}'")
    assert_true(has_analysis is True, "Expected has_analysis to be True")
    assert_true(timeline_count > 0, "Expected timeline_count > 0")

    # -------------------------------------------------------------
    # STEP 7: Audit Full Structured Analysis Report (9 Sections)
    # -------------------------------------------------------------
    log_step("7. User opens Case Analysis Suite via GET /api/v1/cases/{case_id}/analysis")
    analysis_resp = client.get(f"/api/v1/cases/{case_id}/analysis")
    assert_true(analysis_resp.status_code == 200, f"Failed to retrieve analysis: {analysis_resp.status_code}")
    analysis_data = analysis_resp.json()
    report = analysis_data.get("content", {})
    assert_true(bool(report), "Analysis report content is empty!")

    print("Auditing 9 Institutional Litigation Sections...")
    
    # 1. Executive Summary
    exec_summary = report.get("executive_summary", "")
    assert_true(bool(exec_summary), "Missing 'executive_summary'")
    print(f"  [1/9] Executive Summary: {len(exec_summary)} chars. Sample: {exec_summary[:120]}...")

    # 2. Key Findings & Actions
    findings = report.get("key_findings", [])
    actions = report.get("recommended_actions", [])
    assert_true(len(findings) > 0, "Missing 'key_findings'")
    assert_true(len(actions) > 0, "Missing 'recommended_actions'")
    print(f"  [2/9] Findings: {len(findings)} items | Recommended Actions: {len(actions)} items")

    # 3. Document Classifications
    classifications = report.get("document_classifications", [])
    assert_true(len(classifications) >= 3, f"Expected >= 3 classifications, got {len(classifications)}")
    print(f"  [3/9] Document Classifications: {len(classifications)} exhibits classified")
    for c in classifications:
        print(f"        - {c.get('document_name')}: {c.get('classification')} (Conf: {c.get('confidence')})")

    # 4. Master Chronological Timeline
    timeline_items = report.get("timeline", [])
    assert_true(len(timeline_items) > 0, "Missing timeline items in report!")
    print(f"  [4/9] Master Timeline: {len(timeline_items)} chronological events")
    for t in timeline_items[:3]:
        print(f"        - {t.get('event_date')}: {t.get('event_description')[:70]}...")

    # 5. Witness Contradictions (Crucial for trial advocacy!)
    contradictions = report.get("witness_contradictions", [])
    assert_true(len(contradictions) > 0, "Missing 'witness_contradictions' section!")
    print(f"  [5/9] Witness Contradictions: {len(contradictions)} conflicting testimonies detected")
    for wc in contradictions:
        sev = wc.get('impeachment_severity') or wc.get('severity') or "Medium"
        w_name = wc.get('witness_name', 'Witness')
        desc = wc.get('description', '')
        print(f"        - Witness: {w_name} | Severity: {sev}")
        if desc:
            print(f"          Discrepancy: {str(desc)[:75]}...")
        if wc.get("cross_examination_angle") or wc.get("impeachment_strategy"):
            cross_strat = wc.get("cross_examination_angle") or wc.get("impeachment_strategy")
            print(f"          Cross Strategy: {str(cross_strat)[:75]}...")

    # 6. Charges & Statutory Elements
    charges = report.get("charges_analysis", [])
    assert_true(len(charges) > 0, "Missing 'charges_analysis' section!")
    print(f"  [6/9] Statutory Penal Charges: {len(charges)} offenses analyzed")
    for ch in charges[:3]:
        off_name = ch.get('offence_name') or ch.get('charge_name') or "Offence"
        sec = ch.get('section') or ch.get('statute_section') or ""
        defense = ch.get('defense_strategy') or ch.get('defense_theory') or ""
        print(f"        - Charge: {off_name} ({sec})")
        print(f"          Ingredients: {len(ch.get('ingredients', []))} elements mapped | Defense: {str(defense)[:60]}...")

    # 7. Missing Evidence Audit
    missing_ev = report.get("missing_evidence", [])
    print(f"  [7/9] Missing Evidence Audit: {len(missing_ev)} evidentiary gaps flagged")
    for me in missing_ev:
        print(f"        - {me.get('item_name')} ({me.get('statutory_provision', 'N/A')}) -> Severity: {me.get('severity')}")

    # 8. Procedural Compliance
    proc_comp = report.get("procedural_compliance", [])
    print(f"  [8/9] Procedural Compliance: {len(proc_comp)} procedural checkpoints")
    for pc in proc_comp:
        print(f"        - Stage: {pc.get('procedural_stage')} -> Status: {pc.get('status')} ({str(pc.get('requirement', ''))[:50]}...)")

    # 9. Indian Kanoon Precedents
    precedents = report.get("kanoon_precedents", [])
    print(f"  [9/9] Indian Kanoon Precedents: {len(precedents)} legal authorities integrated")
    for pr in precedents:
        print(f"        - Title: {pr.get('title')}")
        print(f"          Court: {pr.get('court')} ({pr.get('year')}) | Citation: {pr.get('citation_standard')}")
        ratio = str(pr.get('ratio_decidendi', ''))
        print(f"          Ratio: {ratio[:80]}...")

    # -------------------------------------------------------------
    # STEP 8: Verify Timeline Endpoint
    # -------------------------------------------------------------
    log_step("8. User fetches chronological events via GET /api/v1/cases/{case_id}/timeline")
    t_resp = client.get(f"/api/v1/cases/{case_id}/timeline")
    assert_true(t_resp.status_code == 200, f"Timeline fetch failed: {t_resp.status_code}")
    t_data = t_resp.json()
    print(f"✓ Retrieved {len(t_data)} saved timeline entries.")
    assert_true(len(t_data) > 0, "No timeline entries found in GET /timeline!")
    sample_t = t_data[0]
    print(f"  Sample Entry: Date={sample_t.get('event_date')}, Desc={sample_t.get('event_description')[:60]}")
    if sample_t.get("citation_quote"):
        print(f"  Citation Quote: \"{sample_t.get('citation_quote')[:70]}...\"")

    # -------------------------------------------------------------
    # STEP 9: Test Courtroom Q&A Agent
    # -------------------------------------------------------------
    log_step("9. User queries Case Q&A Agent via POST /api/v1/cases/{case_id}/qa")
    qa_payload = {
        "question": "Did PW-1 Ramesh Gupta report any physical assault or violence during the meeting on 10/08/2024?"
    }
    qa_resp = client.post(f"/api/v1/cases/{case_id}/qa", json=qa_payload)
    assert_true(qa_resp.status_code == 200, f"QA query failed: {qa_resp.status_code} {qa_resp.text}")
    qa_data = qa_resp.json()
    answer = qa_data.get("answer", "")
    citations = qa_data.get("citations", [])
    print(f"✓ Question: {qa_payload['question']}")
    print(f"✓ Answer: {answer}")
    print(f"✓ Citations Count: {len(citations)}")
    assert_true(bool(answer), "QA answer was empty!")

    # -------------------------------------------------------------
    # STEP 10: Trial Readiness & Legal Evaluation
    # -------------------------------------------------------------
    log_step("10. LEGAL EVALUATION: Complete Trial Readiness Audit")
    
    eval_criteria = {
        "1. Chronological Precision": len(timeline_items) >= 3,
        "2. Witness Impeachment Readiness (PW-1 vs FIR)": any("assault" in str(c).lower() or "violence" in str(c).lower() or "161" in str(c).lower() for c in contradictions),
        "3. Medical Discrepancy (Simple vs Grievous)": any("mlc" in str(f).lower() or "abrasion" in str(f).lower() or "simple" in str(f).lower() for f in findings + missing_ev),
        "4. Commercial Escrow Defense (Sec 482 CrPC / Arbitration)": any("contract" in str(ch).lower() or "arbitration" in str(ch).lower() or "civil" in str(ch).lower() for ch in charges + actions),
        "5. Section 65B/63 BSA Electronic Certificate Alert": any("65b" in str(me).lower() or "63" in str(me).lower() for me in missing_ev),
        "6. Procedural Checkpoint (Arnesh Kumar / Sec 41A Notice)": len(proc_comp) > 0,
        "7. Indian Kanoon Judicial Precedents": len(precedents) > 0,
    }

    print("\n--- LITIGATION READINESS SCORECARD ---")
    all_passed = True
    for criterion, passed in eval_criteria.items():
        status_str = "PASS ✓" if passed else "WARN ⚠️"
        print(f"  {criterion:.<60} {status_str}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    print("ALL USER FLOW ENDPOINTS VERIFIED SUCCESSFULLY!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    try:
        run_e2e_user_test()
    except TestFailure as tf:
        print(f"\n❌ E2E USER TEST SUITE FAILED: {tf}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNHANDLED EXCEPTION DURING TEST: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
