# ALAS Legal AI Empirical Evaluation Framework & Benchmark Suite

An institutional-grade, reproducible evaluation framework for the **AI Legal Assistant Suite (ALAS)**. 
This benchmark suite quantitatively measures every subsystem of ALAS against peer-reviewed academic standards, records empirical performance across language model tiers, and automatically formats the results for direct inclusion in the research paper (`paper.tex`).

---

## 1. Academic Standards & Benchmark Methodologies

Every module in ALAS is mapped to an established peer-reviewed legal AI or NLP evaluation standard:

| # | System Subsystem | Academic Benchmark / Standard | Primary Metrics | Baseline Literature |
|---|---|---|---|---|
| **1** | **Contract Clause Analysis** | **CUAD** (Contract Understanding Atticus Dataset) & **LEDGAR** | Precision, Recall, Macro $F_1$, Micro $F_1$, Token Overlap $F_1$ | Hendrycks et al. (*NeurIPS 2021*); Tuggener et al. (*LREC 2020*) |
| **2** | **Case Document Classifier** | **LexGLUE** & **ILDC** (Indian Legal Documents Corpus) | Multi-class Precision, Recall, $F_1$-score, Macro/Micro Average | Chalkidis et al. (*ACL 2022*); Malik et al. (*ACL 2021*) |
| **3** | **Jurist RAG (Question Answering)** | **RAGAS** & **LegalBench-RAG** | Faithfulness, Answer Relevance, Context Precision, Context Recall | Es et al. (*EACL 2024*); Pipitone et al. (*2024*) |
| **4** | **Litigation Timeline Agent** | **TempEval-3** & **TimeML** Event Extraction | Event Date Jaccard Similarity $J(A,B)$, Kendall's Tau ($\tau$), Milestone $F_1$ | UzZaman et al. (*SemEval 2013*); Pustejovsky et al. (*2003*) |
| **5** | **Witness Contradiction Agent** | **ContractNLI** & **Legal NLI** / Fact Checking | Contradiction Precision, Recall, $F_1$, False Positive Rate, Cohen's Kappa ($\kappa$) | Koreeda & Manning (*EMNLP 2021*); Guha et al. (*LegalBench 2023*) |
| **6** | **Contract Drafting & Redlining** | **Statutory Compliance & Legal DevOps** | Section 27 ICA Non-Compete Remedy Rate, Section 74 Penalty Cap Rate, Kanoon Citation Authenticity | Indian Contract Act, 1872; *Kailash Nath v. DDA*; *Percept D'Mark* |
| **7** | **Pre-Trial Moot Court Debate** | **Adversarial Legal Argumentation** | Issue Framing Precision, Rebuttal Effectiveness, Indian Kanoon Precedent Authenticity | Rauba (*2026*); Wang et al. (*2024*) |

---

## 2. Mathematical Formulations of Metrics

### A. Classification & Extraction ($F_1$-score)
$$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}$$
$$F_1\text{-score} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$
$$\text{Macro } F_1 = \frac{1}{N}\sum_{i=1}^N F_{1, i}, \quad \text{Micro } F_1 = \frac{2 \sum TP_i}{2 \sum TP_i + \sum FP_i + \sum FN_i}$$

### B. RAGAS Quality Metrics
1. **Faithfulness**:
   $$\text{Faithfulness} = \frac{|\text{Number of Claims in Answer Supported by Retrieved Chunks}|}{|\text{Total Claims in Answer}|}$$
2. **Answer Relevance**: Semantic similarity between query $q$ and generated answer $a$, penalized for irrelevant length or missing legal core concepts.
3. **Context Precision@K**:
   $$\text{Context Precision@K} = \frac{\sum_{k=1}^K (\text{Precision@k} \times v_k)}{\text{Total Relevant Chunks in Top K}}$$
   where $v_k \in \{0, 1\}$ indicates ground-truth relevance of the chunk at rank $k$.
4. **Context Recall**:
   $$\text{Context Recall} = \frac{|\text{Retrieved Ground Truth Legal Facts}|}{|\text{All Ground Truth Legal Facts}|}$$

### C. Timeline Extraction (Jaccard Similarity & Kendall's Tau)
$$\text{Jaccard Similarity } J(D_{\text{pred}}, D_{\text{gold}}) = \frac{|D_{\text{pred}} \cap D_{\text{gold}}|}{|D_{\text{pred}} \cup D_{\text{gold}}|}$$
$$\text{Kendall's Tau } \tau = \frac{C - D}{\frac{1}{2} n (n - 1)}$$
where $C$ is the count of concordant pairs and $D$ is the count of discordant pairs in chronological order.

### D. Inter-Rater Reliability (Cohen's Kappa)
$$\kappa = \frac{p_o - p_e}{1 - p_e}$$
where $p_o$ is the observed percentage agreement between independent legal practitioners, and $p_e$ is the hypothetical probability of chance agreement.

---

## 3. Directory Architecture

```
evaluation/
├── README.md                            <- This comprehensive documentation file
├── requirements-eval.txt                <- Python dependencies
├── run_all_evaluations.py               <- Master test runner executing all module benchmarks
├── export_paper_tables.py               <- Exporter updating LaTeX tables in paper.tex
├── benchmarks/                          <- Standardized gold ground-truth datasets
│   ├── gold_contract_clauses.json       <- 22-class CUAD-aligned contract clauses
│   ├── gold_case_documents.json         <- 9-class Indian litigation document files
│   ├── gold_rag_qa_pairs.json           <- 50 Legal QA pairs with context & facts
│   ├── gold_litigation_timelines.json   <- Chronological milestones & event dates
│   ├── gold_witness_contradictions.json <- Witness statements, FIRs & medical contradictions
│   ├── gold_statutory_drafting_redlines.json <- Problematic clauses with statutory traps
│   └── gold_trial_debate_scenarios.json <- Contentious litigation issues & precedents
├── metrics/                             <- Mathematical metric implementations
│   ├── __init__.py
│   ├── classification_metrics.py        <- Precision, Recall, Macro/Micro F1, Token F1
│   ├── ragas_metrics.py                 <- Faithfulness, Answer Relevance, Context P/R
│   ├── temporal_metrics.py              <- Jaccard date similarity & Kendall's Tau
│   ├── contradiction_metrics.py         <- Contradiction F1 & Cohen's Kappa
│   ├── statutory_compliance_metrics.py  <- ICA 1872 compliance & Kanoon authenticity
│   └── system_latency_metrics.py        <- Latency percentiles (p50, p95) & throughput
└── runners/                             <- Standalone test scripts for each module
    ├── __init__.py
    ├── eval_clause_extraction.py        <- Runs contract clause benchmark
    ├── eval_case_classification.py      <- Runs case document classifier benchmark
    ├── eval_jurist_rag.py               <- Runs RAGAS evaluation across 3 model tiers
    ├── eval_timeline_and_witness.py     <- Runs timeline & witness contradiction benchmark
    ├── eval_contract_drafting.py        <- Runs statutory redline verification
    └── eval_trial_debate.py             <- Runs pre-trial moot court evaluation
```

---

## 4. How to Execute Evaluations

The suite supports two execution modes:
1. **Simulation / Verification Mode (Default)**: Validates metrics, schemas, and benchmark logic deterministically without spending LLM API credits.
2. **Live Production Mode (`--live`)**: Connects directly to ALAS backend models (`mistral-medium`, `ministral-14b`, `pixtral-12b`) to run live inferences.

### Run All Modules
```powershell
# In project root:
.\venv\Scripts\python.exe evaluation\run_all_evaluations.py
```

To run with live LLM API calls:
```powershell
.\venv\Scripts\python.exe evaluation\run_all_evaluations.py --live
```

### Run an Individual Module
```powershell
# 1. Contract Clause Extraction (CUAD 22 classes)
.\venv\Scripts\python.exe evaluation\runners\eval_clause_extraction.py

# 2. Case Document Classifier (9 classes)
.\venv\Scripts\python.exe evaluation\runners\eval_case_classification.py

# 3. Jurist RAG (RAGAS framework across 3 model tiers)
.\venv\Scripts\python.exe evaluation\runners\eval_jurist_rag.py

# 4. Litigation Timeline & Witness Contradictions
.\venv\Scripts\python.exe evaluation\runners\eval_timeline_and_witness.py

# 5. Contract Drafting & Statutory Redlines
.\venv\Scripts\python.exe evaluation\runners\eval_contract_drafting.py

# 6. Courtroom Moot Debate Simulation
.\venv\Scripts\python.exe evaluation\runners\eval_trial_debate.py
```

---

## 5. Automated Publication Table Export into `paper.tex`

Once `evaluation_results_master.json` is generated, you can format and inject the real empirical results directly into `paper.tex`:

### Preview LaTeX Tables in Console:
```powershell
.\venv\Scripts\python.exe evaluation\export_paper_tables.py --print-only
```

### Automatically Update `paper.tex`:
```powershell
.\venv\Scripts\python.exe evaluation\export_paper_tables.py --update-paper
```

This updates:
- **`\label{tab:rag_evaluation}`**: Table 1 (RAGAS metrics across Mistral Medium, Ministral 14B, Pixtral 12B)
- **`\label{tab:clause_performance}`**: Table 2 (Precision, Recall, F1 for Limitation of Liability, Indemnification, Governing Law, Dispute Resolution, Force Majeure, Confidentiality, IP, Payment, Termination, Macro/Micro Avg)
- **`\label{tab:doc_classification}`**: Table 3 (FIR, Court Order, Charge Sheet, Witness Statement, Forensic Report, Evidence Photo, Legal Notice, Petition/Affidavit, Other)

