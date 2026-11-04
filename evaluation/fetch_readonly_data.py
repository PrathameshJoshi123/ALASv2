"""
Read-Only Data Extraction Script for ALAS Evaluation.

Strictly executes read-only SELECT queries to fetch target records from the database
without modifying or updating the database in any way.
Persists the fetched snapshot locally to 'evaluation/results/target_db_snapshot.json'.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from sqlalchemy import create_engine, text
from backend.config import settings


def serialize_val(val):
    if isinstance(val, (datetime,)):
        return val.isoformat()
    return val


def mapping_to_dict(m):
    return {k: serialize_val(v) for k, v in m.items()}


def fetch_target_data():
    db_url = settings.database_url
    print(f"Connecting to database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    
    engine = create_engine(db_url, echo=False)
    snapshot = {
        "extracted_at": datetime.now().isoformat(),
        "contract_analysis_doc_id": "b99601bc-84a3-4095-8f75-a1d6b0742b28",
        "drafting_editor_doc_id": "b952d338-8531-437e-ade6-7cd962bb7f99",
        "case_file_id": "57e1a975-64f5-498f-bd9e-e85dd8731a5c",
        "contract_analysis": {},
        "drafting_analysis": {},
        "case_file": {},
    }

    with engine.connect() as conn:
        # Guarantee read-only transaction on PostgreSQL
        if "postgresql" in db_url:
            conn.execute(text("SET TRANSACTION READ ONLY;"))

        # -------------------------------------------------------------
        # 1. Target: b99601bc-84a3-4095-8f75-a1d6b0742b28 (Contract Analysis)
        # -------------------------------------------------------------
        doc_id_1 = "b99601bc-84a3-4095-8f75-a1d6b0742b28"
        print(f"\n[1/3] Fetching Contract Analysis for Doc ID: {doc_id_1}...")

        # Document record
        res = conn.execute(text("SELECT * FROM documents WHERE id = :id"), {"id": doc_id_1})
        row = res.fetchone()
        snapshot["contract_analysis"]["document"] = mapping_to_dict(row._mapping) if row else None

        # Contract Analysis record
        res = conn.execute(text("SELECT * FROM contract_analysis WHERE document_id = :id"), {"id": doc_id_1})
        row = res.fetchone()
        snapshot["contract_analysis"]["analysis"] = mapping_to_dict(row._mapping) if row else None

        # Contract Clauses
        res = conn.execute(
            text("SELECT * FROM contract_clauses WHERE document_id = :id ORDER BY clause_number ASC"),
            {"id": doc_id_1}
        )
        clauses = [mapping_to_dict(r._mapping) for r in res.fetchall()]
        snapshot["contract_analysis"]["clauses"] = clauses

        # Contract Obligations
        res = conn.execute(text("SELECT * FROM contract_obligations WHERE document_id = :id"), {"id": doc_id_1})
        obligations = [mapping_to_dict(r._mapping) for r in res.fetchall()]
        snapshot["contract_analysis"]["obligations"] = obligations

        # Contract Risks
        res = conn.execute(text("SELECT * FROM contract_risks WHERE document_id = :id"), {"id": doc_id_1})
        risks = [mapping_to_dict(r._mapping) for r in res.fetchall()]
        snapshot["contract_analysis"]["risks"] = risks

        # Chunks summary
        try:
            res = conn.execute(
                text("SELECT * FROM chunks WHERE document_id = :id"),
                {"id": doc_id_1}
            )
            chunks = [mapping_to_dict(r._mapping) for r in res.fetchall()]
        except Exception:
            chunks = []
        snapshot["contract_analysis"]["chunks"] = chunks

        print(f"  ✓ Document: {snapshot['contract_analysis']['document'].get('name') if snapshot['contract_analysis']['document'] else 'None'}")
        print(f"  ✓ Analysis found: {bool(snapshot['contract_analysis']['analysis'])}")
        print(f"  ✓ Clauses: {len(clauses)}")
        print(f"  ✓ Obligations: {len(obligations)}")
        print(f"  ✓ Risks: {len(risks)}")
        print(f"  ✓ Chunks: {len(chunks)}")

        # -------------------------------------------------------------
        # 2. Target: b952d338-8531-437e-ade6-7cd962bb7f99 (Drafting / Editor)
        # -------------------------------------------------------------
        doc_id_2 = "b952d338-8531-437e-ade6-7cd962bb7f99"
        print(f"\n[2/3] Fetching Drafting / Analysis for ID: {doc_id_2}...")

        # Check in contract_drafts
        res = conn.execute(
            text("SELECT * FROM contract_drafts WHERE id = :id OR document_id = :id"),
            {"id": doc_id_2}
        )
        row = res.fetchone()
        snapshot["drafting_analysis"]["draft"] = mapping_to_dict(row._mapping) if row else None

        # Check in documents
        res = conn.execute(text("SELECT * FROM documents WHERE id = :id"), {"id": doc_id_2})
        row = res.fetchone()
        snapshot["drafting_analysis"]["document"] = mapping_to_dict(row._mapping) if row else None

        # Check in contract_analysis
        res = conn.execute(text("SELECT * FROM contract_analysis WHERE document_id = :id"), {"id": doc_id_2})
        row = res.fetchone()
        snapshot["drafting_analysis"]["analysis"] = mapping_to_dict(row._mapping) if row else None

        # Check in contract_clauses
        res = conn.execute(text("SELECT * FROM contract_clauses WHERE document_id = :id ORDER BY clause_number ASC"), {"id": doc_id_2})
        clauses2 = [mapping_to_dict(r._mapping) for r in res.fetchall()]
        snapshot["drafting_analysis"]["clauses"] = clauses2

        # Check draft versions
        if snapshot["drafting_analysis"]["draft"]:
            draft_id = snapshot["drafting_analysis"]["draft"]["id"]
            try:
                res = conn.execute(text("SELECT * FROM contract_draft_versions WHERE draft_id = :d_id ORDER BY version_number ASC"), {"d_id": draft_id})
                versions = [mapping_to_dict(r._mapping) for r in res.fetchall()]
            except Exception:
                versions = []
            snapshot["drafting_analysis"]["versions"] = versions
        else:
            snapshot["drafting_analysis"]["versions"] = []

        print(f"  ✓ Draft found: {bool(snapshot['drafting_analysis']['draft'])}")
        print(f"  ✓ Document found: {bool(snapshot['drafting_analysis']['document'])}")
        print(f"  ✓ Analysis found: {bool(snapshot['drafting_analysis']['analysis'])}")
        print(f"  ✓ Clauses found: {len(clauses2)}")

        # -------------------------------------------------------------
        # 3. Target: 57e1a975-64f5-498f-bd9e-e85dd8731a5c (Case Files)
        # -------------------------------------------------------------
        case_id = "57e1a975-64f5-498f-bd9e-e85dd8731a5c"
        print(f"\n[3/3] Fetching Case File for ID: {case_id}...")

        # Case record
        res = conn.execute(text("SELECT * FROM cases WHERE id = :id"), {"id": case_id})
        row = res.fetchone()
        snapshot["case_file"]["case"] = mapping_to_dict(row._mapping) if row else None

        # Case documents
        res = conn.execute(text("SELECT * FROM case_documents WHERE case_id = :id"), {"id": case_id})
        case_docs = [mapping_to_dict(r._mapping) for r in res.fetchall()]
        snapshot["case_file"]["documents"] = case_docs

        # Case timelines
        res = conn.execute(text("SELECT * FROM case_timelines WHERE case_id = :id ORDER BY event_date ASC"), {"id": case_id})
        timelines = [mapping_to_dict(r._mapping) for r in res.fetchall()]
        snapshot["case_file"]["timelines"] = timelines

        # Case analyses
        res = conn.execute(text("SELECT * FROM case_analyses WHERE case_id = :id"), {"id": case_id})
        case_analyses = [mapping_to_dict(r._mapping) for r in res.fetchall()]
        snapshot["case_file"]["analyses"] = case_analyses

        # Case agent memories (logs, findings, contradictions, charges)
        res = conn.execute(text("SELECT * FROM case_agent_memories WHERE case_id = :id"), {"id": case_id})
        memories = [mapping_to_dict(r._mapping) for r in res.fetchall()]
        snapshot["case_file"]["memories"] = memories

        # Evidence details
        try:
            res = conn.execute(text("SELECT * FROM evidence_details WHERE case_id = :id"), {"id": case_id})
            evidence = [mapping_to_dict(r._mapping) for r in res.fetchall()]
        except Exception:
            evidence = []
        snapshot["case_file"]["evidence_details"] = evidence

        print(f"  ✓ Case title: {snapshot['case_file']['case'].get('title') if snapshot['case_file']['case'] else 'None'}")
        print(f"  ✓ Case documents: {len(case_docs)}")
        print(f"  ✓ Timeline events: {len(timelines)}")
        print(f"  ✓ Case analyses: {len(case_analyses)}")
        print(f"  ✓ Agent memories: {len(memories)}")
        print(f"  ✓ Evidence details: {len(evidence)}")

    out_file = PROJECT_ROOT / "evaluation" / "results" / "target_db_snapshot.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    print(f"\n=======================================================")
    print(f"✓ READ-ONLY DB SNAPSHOT SAVED LOCALLY: {out_file}")
    print(f"✓ ZERO WRITES TO DATABASE PERFORMED")
    print(f"=======================================================\n")
    return snapshot


if __name__ == "__main__":
    fetch_target_data()
