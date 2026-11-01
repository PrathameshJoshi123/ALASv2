# Dummy Legal Case Files for ALAS Testing

This directory contains realistic, authentic Indian legal case files specifically constructed to test all capabilities of the **ALAS Case Files Intelligence Engine** (`/dashboard/cases`).

---

## 🏛️ Case Matter Overview
- **Matter Caption**: *State (NCT of Delhi) & Apex FinTech Innovations Ltd. vs. Zenith Cloud Technologies Pvt. Ltd. & Ors.*
- **FIR Number**: 0412/2024 (PS Mandir Marg / Economic Offences Wing, New Delhi)
- **Jurisdiction**: Hon'ble High Court of Delhi (Criminal Miscellaneous Main / Commercial Quashing under Section 482 CrPC / Section 528 BNSS)
- **Subject**: Alleged INR 4.25 Crore software escrow fraud vs. bona fide civil commercial milestone dispute with contractual arbitration clause.

---

## 📁 File Manifest & Targeted ALAS Intelligence Agents

| # | File Name | Document Type | Key Intelligence Triggers |
|---|---|---|---|
| 1 | `01_FIR_No_0412_2024_Mandir_Marg_PS.pdf` | Police FIR (Sec 154 CrPC / Sec 173 BNSS) | **Document Classifier**, **Chronological Timeline**, **Penal Charge Auditing** (Sec 420, 406, 468, 471, 120-B IPC; 318, 316 BNS). Alleges severe assault. |
| 2 | `02_PW1_Statement_Ramesh_Gupta_CFO_Sec161CrPC.pdf` | Witness Statement (Sec 161 CrPC / Sec 180 BNSS) | **Witness Contradiction Agent**: CFO Ramesh Gupta directly contradicts the FIR narrative—states that **no physical assault or violence occurred** on 10/08/2024, and confirms beta software worked properly. |
| 3 | `03_PW2_Statement_Sameer_Verma_CTO_Sec161CrPC.pdf` | Witness Statement (Sec 161 CrPC / Sec 180 BNSS) | **Issue / Charge Agent**: Demonstrates 85,000 lines of code written on AWS, negating fraudulent intent from inception (*Hridaya Ranjan Prasad Verma* doctrine). Explains the accidental wrist graze. |
| 4 | `04_MLC_Medical_Report_Dr_Anurag_Batra_RML_Hospital.pdf` | Medico-Legal Certificate (MLC) | **Contradiction & Missing Evidence Agent**: 34-hour delay in examination; classifies injury as "SIMPLE IN NATURE" (single 1.2cm scratch), debunking grievous assault claims. Flags **lack of Section 65B / 63 BSA certificate** on HIS printout. |
| 5 | `05_Master_Software_Escrow_Agreement_Dated_15012024.pdf` | Commercial Contract | **Contractual Analysis & Legal Research Agent**: Clause 18 contains a mandatory **DIAC Arbitration** clause and caps liquidated damages at 15%, establishing civil remedy bar to criminal prosecution. |
| 6 | `06_Forensic_Audit_Report_and_Seizure_Panchnama.pdf` | Seizure Memo & Panchnama | **Procedural Compliance Agent**: Detects major procedural flaws—no independent civilian panchas (only police officers), failure to generate SHA-256 hash at scene of seizure, violation of Sec 100(4) CrPC. |
| 7 | `07_Evidentiary_WhatsApp_Chat_Screenshot.png` | Digital Image Evidence | **Multimodal Pixtral OCR & Vision Agent**: Tests image OCR and visual analysis. Proves cordial scheduling of 10/08/2024 meeting and pre-disbursement beta testing. |

---

## 🚀 How to Upload & Test in ALAS UI

1. **Start ALAS** (Backend & Frontend):
   - Backend: `./start_backend.ps1` (or `uvicorn backend.main:app --reload --port 8000`)
   - Frontend: `cd frontend && pnpm run dev`
2. **Open the Case Files Dashboard**:
   - Navigate to: `http://localhost:3000/dashboard/cases`
3. **Create a Case File**:
   - Click **"Create New Case File"** (or "+ New Case").
   - Title: `State & Apex FinTech vs. Zenith Cloud Technologies (FIR 0412/2024)`
   - Description: `Alleged software escrow cheating under Sec 420/406 IPC vs commercial milestone dispute with DIAC arbitration.`
4. **Upload the Files**:
   - In the Case Workspace, click **"Upload Documents"**.
   - Browse to this directory: `c:\Users\Prajwal\code\ALASv2\dummy_case_files\`
   - Select all 7 files (or upload them individually).
5. **Run AI Multi-Agent Intelligence**:
   - Click **"Run Comprehensive Analysis"**.
   - The LangGraph Orchestrator will execute:
     - Document Classifier
     - Timeline Agent (Chronological events from 15/01/2024 to 24/08/2024)
     - Witness Contradiction Agent (Highlighting FIR vs. CFO vs. MLC contradictions)
     - Penal Ingredient Auditor (IPC vs BNS statutory element analysis)
     - Procedural Compliance Auditor (Missing 65B certificates, improper panchnama)
     - Precedent Research (Searching *Indian Kanoon* for *Hridaya Ranjan Prasad Verma*, *Arnesh Kumar*, etc.)
6. **Interact with Pre-Trial Tools**:
   - **Case Q&A**: Ask *"Did any physical assault occur during the August 10 meeting?"* or *"What procedural defects exist in the seizure memo?"*
   - **Adversarial Courtroom Debate**: Run Prosecution vs. Defence debate to view judge verdict and legal strategy recommendations!
