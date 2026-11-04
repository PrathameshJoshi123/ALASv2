"""
Master Evaluation Suite Runner for ALAS (AI Legal Assistant Suite).

Executes comprehensive evaluation across all project modules:
1. Contract Clause Classification (CUAD / LEDGAR 22-class standard)
2. Case Document Classification (LexGLUE / ILDC 9-class standard)
3. Jurist RAG Retrieval & Generation Quality (RAGAS framework across 3 model tiers)
4. Chronological Timeline & Milestone Integrity (TempEval-3 / TimeML standard)
5. Witness Testimony Contradiction Analysis (Legal NLI standard)
6. Contract Drafting & Statutory Redline Verification (ICA 1872 & Precedent compliance)
7. Pre-Trial Adversarial Courtroom Moot Debate (Argumentation & Citation authenticity)

Saves consolidated empirical results to 'evaluation_results_master.json'.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.runners.eval_clause_extraction import run_clause_evaluation
from evaluation.runners.eval_case_classification import run_case_classification_evaluation
from evaluation.runners.eval_jurist_rag import run_rag_evaluation
from evaluation.runners.eval_timeline_and_witness import run_timeline_and_witness_evaluation
from evaluation.runners.eval_contract_drafting import run_contract_drafting_evaluation
from evaluation.runners.eval_trial_debate import run_trial_debate_evaluation


def run_full_suite(live: bool = False, output_file: Optional[str] = None) -> dict:
    """Execute all benchmarks and save consolidated results."""
    start_time = time.time()
    timestamp = datetime.now().isoformat()

    print("\n" + "=" * 90)
    print("ALAS EMPIRICAL BENCHMARK EVALUATION SUITE")
    print(f"Timestamp: {timestamp}")
    print(f"Execution Mode: {'LIVE PRODUCTION LLMs' if live else 'DETERMINISTIC BENCHMARK SIMULATION'}")
    print("=" * 90 + "\n")

    results = {
        "metadata": {
            "timestamp": timestamp,
            "mode": "live" if live else "simulation",
            "suite_version": "1.0.0",
        },
        "modules": {}
    }

    # 1. Clause Classification
    print("\n[MODULE 1/6] Evaluating Contract Clause Extraction...")
    clause_results = run_clause_evaluation(live=live)
    results["modules"]["clause_classification"] = clause_results

    # 2. Case Document Classification
    print("\n[MODULE 2/6] Evaluating Case Document Classifier...")
    doc_results = run_case_classification_evaluation(live=live)
    results["modules"]["case_document_classification"] = doc_results

    # 3. Jurist RAG
    print("\n[MODULE 3/6] Evaluating Jurist RAG with RAGAS Framework...")
    rag_results = run_rag_evaluation(live=live)
    results["modules"]["jurist_rag"] = rag_results

    # 4. Timeline & Witness Contradictions
    print("\n[MODULE 4/6] Evaluating Timeline Extraction & Witness Contradictions...")
    timeline_witness_results = run_timeline_and_witness_evaluation(live=live)
    results["modules"]["timeline_and_witness"] = timeline_witness_results

    # 5. Contract Drafting & Redlining
    print("\n[MODULE 5/6] Evaluating Contract Drafting & Statutory Redline Compliance...")
    drafting_results = run_contract_drafting_evaluation(live=live)
    results["modules"]["contract_drafting"] = drafting_results

    # 6. Pre-Trial Courtroom Moot Debate
    print("\n[MODULE 6/6] Evaluating Pre-Trial Adversarial Debate System...")
    debate_results = run_trial_debate_evaluation(live=live)
    results["modules"]["trial_debate"] = debate_results

    total_duration = time.time() - start_time
    results["metadata"]["total_duration_seconds"] = round(total_duration, 2)

    # Save to disk
    out_path = Path(output_file) if output_file else (PROJECT_ROOT / "evaluation" / "evaluation_results_master.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 90)
    print(f"✓ EVALUATION SUITE COMPLETED IN {round(total_duration, 2)} SECONDS")
    print(f"✓ MASTER RESULTS PERSISTED TO: {out_path.resolve()}")
    print("=" * 90 + "\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="ALAS Benchmark Evaluation Harness")
    parser.add_argument("--live", action="store_true", help="Execute live calls against configured LLMs/endpoints")
    parser.add_argument("--output", type=str, default=None, help="Custom output JSON path")
    parser.add_argument("--module", type=str, choices=["all", "clauses", "docs", "rag", "timeline", "drafting", "debate"], default="all")
    args = parser.parse_args()

    if args.module == "all":
        run_full_suite(live=args.live, output_file=args.output)
    elif args.module == "clauses":
        run_clause_evaluation(live=args.live)
    elif args.module == "docs":
        run_case_classification_evaluation(live=args.live)
    elif args.module == "rag":
        run_rag_evaluation(live=args.live)
    elif args.module == "timeline":
        run_timeline_and_witness_evaluation(live=args.live)
    elif args.module == "drafting":
        run_contract_drafting_evaluation(live=args.live)
    elif args.module == "debate":
        run_trial_debate_evaluation(live=args.live)


if __name__ == "__main__":
    main()

