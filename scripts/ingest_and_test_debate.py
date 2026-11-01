"""
Ingest Case Dossier and Test Pre-Trial Adversarial Debate LangGraph Engine.

Steps:
1. Seed the Apex FinTech vs. Zenith Cloud Technologies case in Supabase DB.
2. Attach the 5 generated PDF documents, timelines, and charge analyses.
3. Execute the full multi-agent courtroom moot graph:
   - Case Intake & Framing
   - Petitioner Counsel (Offense & Bhajan Lal Doctrine via Kanoon)
   - Respondent Counsel (Demolition & Dalip Kaur Doctrine via Kanoon)
   - Presiding Judicial Bench Interlocutory Challenge
   - Human-in-the-Loop Lead Counsel Intervention & Dynamic Opponent Pivot
   - Pre-Trial Combat Pack Compilation & DB Persistence
4. Verify all generated outputs and debate memory in the database.
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.database import SessionLocal
from backend.models.cases import (
    Case,
    CaseDocument,
    CaseTimeline,
    CaseAnalysis,
    CaseAgentMemory,
)
from backend.agents.trial_debate_langgraph import (
    build_trial_debate_graph,
    node_human_lawyer_intervention,
    TrialDebateState,
)
from backend.services.debate_stream_service import DebateStreamService


def seed_case_dossier() -> str:
    print("\n--- 1. Seeding Authentic Case Dossier in Supabase ---")
    db = SessionLocal()
    try:
        case_id = str(uuid.uuid4())
        case = Case(
            id=case_id,
            title="State & Apex FinTech Ltd. v. Zenith Cloud Technologies Pvt. Ltd.",
            description=(
                "High-stakes commercial fraud litigation arising from fraudulent diversion of INR 4.25 Crores "
                "escrow funds under the pretext of proprietary banking software deployment. Cross-allegations "
                "under Sections 406/420/468/471/120B IPC and quashing petition under Section 482 CrPC."
            ),
            status="analyzed",
        )
        db.add(case)
        db.flush()

        # 2. Attach the 5 PDF documents
        doc_dir = Path("backend/storage/dummy_cases/apex_vs_zenith")
        pdf_files = [
            ("01_FIRST_INFORMATION_REPORT_FIR_0412_2024.pdf", "First Information Report (FIR No. 0412/2024)", "FIR"),
            ("02_MASTER_ESCROW_AND_SOFTWARE_LICENSE_AGREEMENT.pdf", "Master Software Escrow & Deployment Agreement", "CONTRACT"),
            ("03_EVIDENTIARY_RECORD_BANK_ADVICES_AND_ELECTRONIC_TRANSCRIPTS.pdf", "Bank Statements & Digital WhatsApp Transcripts", "EVIDENCE"),
            ("04_LEGAL_DEMAND_NOTICE_AND_REPLY_MEMORANDUM.pdf", "Pre-Litigation Demand & Reply Notice", "LEGAL_NOTICE"),
            ("05_SECTION_482_CRPC_QUASHING_PETITION.pdf", "Section 482 CrPC Quashing Petition (Delhi HC)", "COURT_PETITION"),
        ]

        doc_ids = []
        for filename, doc_name, doc_type in pdf_files:
            file_path = doc_dir / filename
            doc_id = str(uuid.uuid4())
            doc_rec = CaseDocument(
                id=doc_id,
                case_id=case_id,
                name=doc_name,
                storage_link=str(file_path.resolve()),
                file_type="application/pdf",
                document_type=doc_type,
                status="processed",
            )
            db.add(doc_rec)
            doc_ids.append(doc_id)
        db.flush()
        print(f"Created Case {case_id} with {len(doc_ids)} attached PDF legal documents.")

        # 3. Add chronological timeline events
        timeline_events = [
            (datetime(2024, 1, 15), "Execution of Master Software Escrow Agreement between Apex FinTech and Zenith Cloud.", doc_ids[1], 1),
            (datetime(2024, 1, 18), "Apex FinTech disbursed Milestone-1 Tranche of INR 4.25 Crores into designated escrow.", doc_ids[2], 1),
            (datetime(2024, 1, 19), "Zenith diverted INR 2.00 Cr to Malhotra Ventures LLP and INR 2.10 Cr to Dubai shell entity.", doc_ids[2], 1),
            (datetime(2024, 7, 12), "Apex discovered CertiGuard Labs security audit certificate #CG-8829 was completely fictitious.", doc_ids[2], 1),
            (datetime(2024, 7, 15), "Apex served Formal Demand Notice for refund of INR 4.25 Crores with 18% p.a. interest.", doc_ids[3], 1),
            (datetime(2024, 7, 28), "Zenith replied citing AWS supply chain outage and asserting pure civil arbitration under Clause 14.", doc_ids[3], 1),
            (datetime(2024, 8, 14), "Delhi Police EOW registered FIR No. 0412/2024 u/s 406/420/468/471/120B IPC against Rajesh Malhotra & Zenith.", doc_ids[0], 1),
            (datetime(2024, 8, 22), "Zenith filed Criminal Misc. Main Petition under Section 482 CrPC in Delhi High Court seeking quashing.", doc_ids[4], 1),
        ]

        for dt, desc, d_id, page in timeline_events:
            t_rec = CaseTimeline(
                id=str(uuid.uuid4()),
                case_id=case_id,
                event_date=dt,
                event_description=desc,
                source_document_id=d_id,
                source_page=page,
            )
            db.add(t_rec)
        db.flush()
        print(f"Added {len(timeline_events)} timeline records.")

        # 4. Add structured Case Analysis with charges
        analysis_data = {
            "case_summary": "Dispute concerning diversion of INR 4.25 Cr under software agreement with forged audit certificates.",
            "charges_analysis": [
                {
                    "charge_name": "Section 420 IPC / Section 318 BNS (Cheating & Dishonestly Inducing Delivery of Property)",
                    "ingredient_status": "Prima facie fulfilled via forged ISO cert #CG-8829 inducing 4.25 Cr release prior to inception.",
                    "defense_weakness": "Prosecution must overcome defense plea that dispute is civil breach subject to DIAC arbitration.",
                },
                {
                    "charge_name": "Section 406 IPC / Section 316 BNS (Criminal Breach of Trust in Escrow Custody)",
                    "ingredient_status": "Fulfilled via immediate fund diversion to Malhotra Ventures LLP within 48 hours of credit.",
                    "defense_weakness": "Defense argues escrow release covenants permitted infrastructure expenditure.",
                },
                {
                    "charge_name": "Section 65B Indian Evidence Act / Section 63 BSA (Admissibility of WhatsApp Transcripts)",
                    "ingredient_status": "Deficient: Transcripts in Exhibit P-2 lack mandatory digital signature certificate.",
                    "defense_weakness": "Threshold admissibility bar under Supreme Court ruling in Arjun Panditrao Khotkar.",
                },
            ],
        }

        case_analysis = CaseAnalysis(
            id=str(uuid.uuid4()),
            case_id=case_id,
            analysis_type="full_case_analysis",
            content=analysis_data,
        )
        db.add(case_analysis)
        db.commit()
        print("Persisted full CaseAnalysis records to Supabase.")
        return case_id
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def test_debate_engine(case_id: str):
    print("\n--- 2. Executing Pre-Trial Debate LangGraph Simulation ---")
    graph = build_trial_debate_graph()

    initial_state: TrialDebateState = {
        "case_id": case_id,
        "matter_title": "State & Apex FinTech Ltd. v. Zenith Cloud Technologies Pvt. Ltd.",
        "case_facts": "",
        "framed_issues": [],
        "current_round": 1,
        "max_rounds": 2,
        "active_speaker": "petitioner",
        "debate_turns": [],
        "bench_queries": [],
        "all_citations": [],
        "momentum_petitioner": 55,
        "human_intervention_pending": False,
        "user_custom_argument": None,
        "user_represented_side": "petitioner",
        "is_completed": False,
        "final_combat_brief": {},
    }

    print("Invoking LangGraph moot engine...")
    final_state = graph.invoke(initial_state)

    print("\n--- 3. Verifying Multi-Agent Debate Outputs ---")
    print(f"Framed Issues ({len(final_state['framed_issues'])}):")
    for idx, iss in enumerate(final_state["framed_issues"], 1):
        print(f"  [{idx}] {iss}")

    print(f"\nDebate Turns Recorded: {len(final_state['debate_turns'])}")
    for turn in final_state["debate_turns"]:
        print(f"\n* [{turn['speaker'].upper()}] - {turn['title']}")
        print(f"  Argument: {turn['argument_text'][:160]}...")
        if turn.get("citations"):
            for c in turn["citations"]:
                print(f"  -> Kanoon Authority: {c['title']} | Doc ID: {c['doc_id']} | URL: {c['url']}")

    print(f"\nBench Queries Posed: {len(final_state['bench_queries'])}")
    for bq in final_state["bench_queries"]:
        print(f"\n* [BENCH QUERY to {bq['targeted_speaker'].upper()}]: {bq['query']}")
        print(f"  Context Basis: {bq['context_basis']}")
        print(f"  Evidentiary Flag: {bq.get('evidentiary_flag')}")

    # 4. Test Human Lawyer Intervention
    print("\n--- 4. Testing Human-in-the-Loop Lead Counsel Intervention ---")
    intervention_state = dict(final_state)
    intervention_state["user_custom_argument"] = (
        "Under Section 91 CrPC and Arjun Panditrao Khotkar, the prosecution formally petitions the chamber "
        "to issue summons for production of the primary Samsung server node to cure the Section 65B defect "
        "instantly, rendering the quashing petition infructuous."
    )
    intervention_state["user_represented_side"] = "petitioner"
    intervention_state["human_intervention_pending"] = True

    post_intervention = node_human_lawyer_intervention(intervention_state)
    print(f"Total turns after intervention: {len(post_intervention['debate_turns'])}")
    last_user_turn = post_intervention["debate_turns"][-2]
    last_opp_turn = post_intervention["debate_turns"][-1]
    print(f"\n* User Intervenor: {last_user_turn['title']}")
    print(f"  Text: {last_user_turn['argument_text']}")
    print(f"\n* Autonomous Opponent Pivot: {last_opp_turn['title']}")
    print(f"  Counter-Argument: {last_opp_turn['argument_text']}")
    print(f"  Opponent Kanoon Grounding: {[c['title'] for c in last_opp_turn.get('citations', [])]}")

    # 5. Check Final Pre-Trial Combat Pack in DB
    print("\n--- 5. Checking Persisted Pre-Trial Combat Pack in Supabase CaseAgentMemory ---")
    db = SessionLocal()
    try:
        mem = db.query(CaseAgentMemory).filter(
            CaseAgentMemory.case_id == case_id,
            CaseAgentMemory.memory_key == "trial_debate_brief",
        ).first()

        if mem:
            brief = mem.memory_value
            print(f"Combat Pack Found in DB for Case: {mem.case_id}")
            print(f"Petitioner Win Probability: {brief.get('win_probability_petitioner')}%")
            print(f"Respondent Win Probability: {brief.get('win_probability_respondent')}%")
            print(f"Executive Summary:\n{brief.get('executive_summary')}\n")
            print("Adversary Predicted Playbook:")
            for item in brief.get("adversary_playbook", []):
                print(f"  - Move: {item['predicted_move']}")
                print(f"    Counter: {item['counter_rebuttal']}")
            print(f"Total Citations Ledger: {len(brief.get('citations_ledger', []))} items")
        else:
            print("Warning: trial_debate_brief not found in CaseAgentMemory.")
    finally:
        db.close()

    return case_id


if __name__ == "__main__":
    case_id = seed_case_dossier()
    test_debate_engine(case_id)
    print(f"\nAll Pre-Trial Debate System tests completed successfully for Case ID: {case_id}")
