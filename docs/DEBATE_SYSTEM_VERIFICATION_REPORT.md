# Pre-Trial Adversarial Debate System — Verification & Technical Report

**Project**: ALAS (Autonomous Legal Advisory & Courtroom Simulation Suite)  
**Date**: October 29, 2026  
**Subject Matter**: *State & Apex FinTech Innovations Ltd. v. Zenith Cloud Technologies Pvt. Ltd. & Ors.*  
**Case ID**: `f2fdb651-5e74-4363-b1c7-b82d7e831687`  
**Court Jurisdiction**: Hon'ble High Court of Delhi (Criminal Miscellaneous Main / Commercial Division)  
**UI Route**: `/dashboard/cases/f2fdb651-5e74-4363-b1c7-b82d7e831687/debate`  

---

## 1. Executive Summary

The **Pre-Trial Adversarial Courtroom Debate System** was verified end-to-end against live infrastructure (**FastAPI backend**, **Celery background worker**, **Redis pub/sub broker**, and **Supabase PostgreSQL database**).

To properly test the multi-agent courtroom moot without using confidential case records, a 5-document legal case file in standard PDF format was constructed, placed into the project's persistent storage, uploaded through the official API, chunked/indexed, and simulated through the LangGraph engine.

### Core Simulation Results
- **Framed Legal Issues**: 3 contentious Indian legal issues (Criminal vs. Commercial breach under Section 482 CrPC / Section 528 BNSS, Section 65B Electronic Admissibility, Mens Rea under Section 420 IPC / Section 318 BNS).
- **Prosecution Counsel Agent**: Argued prima facie threshold under the *Bhajan Lal* doctrine, citing live Supreme Court authorities retrieved autonomously from Indian Kanoon (`doc #1288331`).
- **Defense Counsel Agent**: Raised commercial arbitration preemption and lack of initial fraudulent intent under the *Dalip Kaur* and *Indian Oil Corporation* doctrines (`doc #71658549`).
- **Presiding Judicial Bench Agent**: Posed targeted interlocutory challenges flagging the lack of Section 65B digital forensic certification on Exhibit P-3, dynamically shifting petitioner momentum to **57%**.
- **Human-in-the-Loop Lead Counsel Intervention**: Human lawyer intervened with a Section 91 CrPC subpoena motion for primary device inspection; opposing counsel autonomously adapted with counter-rebuttal (`doc #11869944`), shifting momentum to **61%**.
- **Pre-Trial Combat Pack**: Compiled actionable adversary predicted playbooks, bench trap warnings, and Kanoon citation ledgers, successfully persisted to `CaseAgentMemory` in Supabase.
- **Real-Time Streaming**: Verified SSE stream endpoint `/api/v1/cases/{id}/debate/stream` (`text/event-stream` returning `HTTP 200`).

---

## 2. Dummy Case Dossier Architecture

The generated dummy case simulates a commercial-criminal fraud dispute under both the Indian Penal Code (IPC) / Criminal Procedure Code (CrPC) and the Bharatiya Nyaya Sanhita (BNS) / Bharatiya Nagarik Suraksha Sanhita (BNSS).

### Generated PDF Documents (Stored in `backend/storage/dummy_cases/apex_vs_zenith/`)

| # | Document Filename | Legal Type | Key Evidentiary & Statutory Matrix |
|---|-------------------|------------|-----------------------------------|
| **1** | `01_FIRST_INFORMATION_REPORT_FIR_0412_2024.pdf` | FIR (Sec 154 CrPC / 173 BNSS) | EOW Mandir Marg FIR charging Sections 406, 420, 468, 471, 120-B IPC regarding INR 4.25 Cr diversion via bogus security audit cert #CG-8829. |
| **2** | `02_MASTER_ESCROW_AND_SOFTWARE_LICENSE_AGREEMENT.pdf` | Commercial Contract | Master deployment agreement with Clause 3 (Milestones), Clause 7 (Anti-fraud warranties), and Clause 14 (Mandatory DIAC Arbitration in New Delhi). |
| **3** | `03_EVIDENTIARY_RECORD_BANK_ADVICES_AND_ELECTRONIC_TRANSCRIPTS.pdf` | Evidentiary Record | HDFC escrow ledger showing round-tripping to shell entities, WhatsApp transcripts, and an explicit evidentiary deficiency: **lack of Section 65B(4) / Section 63 BSA certificate**. |
| **4** | `04_LEGAL_DEMAND_NOTICE_AND_REPLY_MEMORANDUM.pdf` | Pre-Litigation Notice & Reply | 15-day refund demand by Singhania & Partners; Defense reply by Malhotra Chambers invoking force majeure (AWS outage) and *Dalip Kaur* civil bar. |
| **5** | `05_SECTION_482_CRPC_QUASHING_PETITION.pdf` | High Court Pleading | Crl. Misc. Main petition before Delhi High Court praying to quash FIR 0412/2024 on grounds of civil arbitration clause and inadmissible electronic evidence. |

---

## 3. End-to-End Verification Lifecycle

The verification was conducted as an automated user-emulation script (`scripts/test_user_flow_debate.py`), mirroring the exact HTTP network calls initiated by the Next.js frontend:

```
[User Browser / Next.js]
        │
        ├── 1. POST /api/v1/cases (Create Case) ──────────────► [Supabase DB]
        │
        ├── 2. POST /api/v1/cases/{id}/upload (5 PDFs) ───────► [Storage + Celery Task Queue]
        │                                                              │
        │                                                              ▼
        │                                                    [PDF Parser & Chunker]
        │                                                    [Chroma Vector Store]
        │
        ├── 3. POST /api/v1/cases/{id}/debate/start ──────────► [LangGraph Engine]
        │                                                              │
        │                                                              ├── Issue Framing Node
        │                                                              ├── Petitioner Counsel Node (Kanoon Tool)
        │                                                              ├── Respondent Counsel Node (Kanoon Tool)
        │                                                              ├── Judicial Bench Challenge Node
        │                                                              └── Trial Brief Synthesis Node
        │                                                              │
        │                                                              ▼
        ├── 4. GET /api/v1/cases/{id}/debate/stream (SSE) ◄─── [DebateStreamService]
        │
        ├── 5. POST /api/v1/cases/{id}/debate/turn (Intervene)► [Dynamic Opponent Pivot]
        │
        └── 6. GET /api/v1/cases/{id}/debate/brief ───────────► [Pre-Trial Combat Pack]
```

### Verification Steps & Logs

#### Step 1: Case Creation
- **Endpoint**: `POST /api/v1/cases`
- **Output**: Case created with ID `f2fdb651-5e74-4363-b1c7-b82d7e831687`.

#### Step 2: Multipart Form File Ingestion
- **Endpoint**: `POST /api/v1/cases/{case_id}/upload`
- **Documents Uploaded**:
  - `01_FIRST_INFORMATION_REPORT_FIR_0412_2024.pdf` (Doc ID: `d55a7556-3eb1-431b-aed7-2f9799ddd110`)
  - `02_MASTER_ESCROW_AND_SOFTWARE_LICENSE_AGREEMENT.pdf` (Doc ID: `5010a7f8-0947-424a-99b9-61c0e7ee227c`)
  - `03_EVIDENTIARY_RECORD_BANK_ADVICES_AND_ELECTRONIC_TRANSCRIPTS.pdf` (Doc ID: `c110c844-3115-4c1e-9d11-b8987114e28b`)
  - `04_LEGAL_DEMAND_NOTICE_AND_REPLY_MEMORANDUM.pdf` (Doc ID: `e9cfe74f-257d-470e-b9ff-e7d11388e371`)
  - `05_SECTION_482_CRPC_QUASHING_PETITION.pdf` (Doc ID: `1431410e-bd9f-4111-9beb-1c151bfb3af6`)
- **Celery Worker Execution**: Asynchronously picked up each document ID, executed multimodal extraction, split text chunks via `ChunkingPipeline`, and committed to disk.

#### Step 3: Moot Court Debate Initialization
- **Endpoint**: `POST /api/v1/cases/{case_id}/debate/start`
- **Framed Contentious Issues**:
  1. *Issue 1: Maintainability of Criminal Proceedings in Commercial Dispute (Sec 482 CrPC / Sec 528 BNSS)*
  2. *Issue 2: Admissibility and Certificate Mandate of Electronic Transcripts (Sec 65B BSA / IEA)*
  3. *Issue 3: Prima Facie Establishment of Mens Rea at Inception (Sec 420 IPC / Sec 318 BNS)*
- **Petitioner Oral Pleading (Turn #1)**:
  - *Doctrine*: Prima Facie Cognizability & *Bhajan Lal* Threshold.
  - *Argument Summary*: Pre-trial quashing under Section 482 cannot conduct a mini-trial when allegations disclose fraudulent inducement and fake escrow receipts prior to disbursement.
  - *Authority*: Precedent `doc #1288331` from Indian Kanoon (Supreme Court of India).
- **Defense Oral Pleading (Turn #2)**:
  - *Doctrine*: Absence of Mens Rea & Civil Arbitration Preemption.
  - *Argument Summary*: Relying on *Dalip Kaur v. Jagnar Singh* and *Indian Oil Corporation v. NEPC India*, mere failure to perform cannot be converted into criminal cheating; dispute is governed by Clause 14 arbitration.
  - *Authority*: Precedent `doc #71658549` from Indian Kanoon (Supreme Court of India).
- **Judicial Bench Interlocutory Query**:
  - *Target*: Petitioner Counsel.
  - *Challenge*: *"The parties actively performed under the contract for 7 months. How do you overcome the requirement of proving fraudulent intent existed at the very inception?"*
  - *Evidentiary Defect Flagged*: *"Exhibit P-3 lacks digital forensic hash verification under Sec 65B/63 BSA."*
  - *Suggested Rebuttal Anchor*: *"Anchor on the fraudulent valuation certificate submitted prior to the first disbursement."*

#### Step 4: Human-in-the-Loop Intervenor Execution
- **Endpoint**: `POST /api/v1/cases/{case_id}/debate/turn`
- **Lead Counsel Injected Submission**:
  > *"Under Section 91 CrPC and the ratio in Arjun Panditrao Khotkar, the prosecution formally petitions the court to issue immediate summons to produce the primary server hard-disk for forensic hashing, thereby curing the Section 65B certificate defect and extinguishing respondent's quashing ground."*
- **Autonomous Opponent Counter-Pivot**:
  - Opposing counsel agent executed a real-time Indian Kanoon search on the new proposition, shifted strategy to the "four corners of the record" doctrine (`doc #11869944`), and countered that pre-trial Section 91 summons cannot be used to fish for evidence during quashing.
- **Updated Momentum**: Shifted from **57%** to **61%** in favor of Petitioner.

#### Step 5: Pre-Trial Readiness Brief & Combat Pack Inspection
- **Endpoint**: `GET /api/v1/cases/{case_id}/debate/brief`
- **Persistence**: Saved under `CaseAgentMemory` with key `trial_debate_brief`.
- **Metrics**:
  - Petitioner Win Probability: **57%**
  - Respondent Win Probability: **43%**
  - Kanoon Citation Ledger: 2 Supreme Court authorities indexed with ratios and direct links.
- **Adversary Predicted Playbook**:
  1. *Predicted Move*: Filing Section 482 Quashing petition claiming purely commercial dispute.  
     *Counter-Rebuttal*: Cite *Bhajan Lal* Category 1 (allegations disclose prima facie offense precluding threshold quashing).
  2. *Predicted Move*: Challenging WhatsApp transcripts under *Arjun Panditrao Khotkar* for lack of Section 65B certificate.  
     *Counter-Rebuttal*: File Section 91 CrPC application to produce primary cellular device for direct inspection.

#### Step 6: SSE Stream Verification
- **Endpoint**: `GET /api/v1/cases/{case_id}/debate/stream`
- **Result**: `HTTP 200 OK`, `Content-Type: text/event-stream`.
- Real-time events (`ISSUE_FRAMING_COMPLETED`, `SPEECH_START`, `PETITIONER_ARGUMENT`, `RESPONDENT_REBUTTAL`, `BENCH_QUERY`, `TRIAL_BRIEF_GENERATED`) broadcast through Redis channels and in-memory fallbacks.

---

## 4. Active Service Topology

| Service | Port / Connection | Process ID | Status | Health Check |
|---------|-------------------|------------|--------|--------------|
| **FastAPI Backend (Uvicorn)** | `127.0.0.1:8000` | `15416` | **ONLINE** | `GET /health` -> `HTTP 200` |
| **Celery Worker (`-P solo`)** | Redis Broker | Dedicated Task | **ONLINE** | `GET /celery/health` -> `workers: ["celery@Prathamesh"]` |
| **Redis Server** | `localhost:6379` | Docker Container | **ONLINE** | `PING` -> `PONG` |
| **Supabase PostgreSQL** | `aws-0-ap-northeast-1` | Cloud Pooler | **ONLINE** | `SELECT 1` -> `healthy` |

---

## 5. Frontend Visual Studio Access

The pre-trial debate courtroom interface is accessible in the UI at:
👉 `http://localhost:3000/dashboard/cases/f2fdb651-5e74-4363-b1c7-b82d7e831687/debate`

### Interactive Features Available:
1. **Adversarial Arena**: Side-by-side tabs displaying Petitioner arguments vs. Respondent counter-rebuttals with doctrine pills and Kanoon citation cards.
2. **Bench Interlocutory Log**: Dedicated panel showing judicial challenges and evidentiary warnings.
3. **Kanoon Precedent Inspector**: One-click modal displaying the ratio decidendi, statutory sections, and distinguishing angles.
4. **Human Intervenor Quick Pills**: One-click prompts allowing lead counsel to plead Section 65B inadmissibility, absence of mens rea, or commercial frustration.
5. **Combat Pack Modal**: Downloadable pre-trial tactical dossier with win momentum charts and predicted adversary playbooks.
