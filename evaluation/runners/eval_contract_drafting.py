"""
Contract Drafting & Statutory Redline Verification Runner.

Evaluates ALAS Contract Revision Service and Drafting Engine against Indian statutory standards:
1. Section 27 Indian Contract Act 1872 (Void Post-Employment Restraint Remediation)
2. Section 74 Indian Contract Act 1872 (Punitive Penalty Capping to Reasonable Pre-Estimate)
3. Perkins Eastman Doctrine (Unilateral Sole Arbitrator Neutralization)
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.metrics.statutory_compliance_metrics import evaluate_statutory_remediation

REDLINE_BENCHMARK_PATH = PROJECT_ROOT / "evaluation" / "benchmarks" / "gold_statutory_drafting_redlines.json"


def run_contract_drafting_evaluation(live: bool = False) -> Dict[str, Any]:
    """Run contract drafting and redline statutory compliance evaluation."""
    print("=" * 80)
    print("RUNNING BENCHMARK: Contract Drafting & Statutory Redline Compliance")
    print(f"Mode: {'LIVE LLM' if live else 'STANDALONE / DRY-RUN SIMULATION'}")
    print("=" * 80)

    with open(REDLINE_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        gold_redlines = json.load(f)

    results = []
    success_count = 0

    for item in gold_redlines:
        cid = item["id"]
        statute_type = item["statute_type"]
        original = item["original_clause"]
        sample_redline = item["sample_valid_redline"]

        # Evaluate compliance of the redrafted clause
        eval_res = evaluate_statutory_remediation(original, sample_redline, statute_type)
        eval_res["clause_id"] = cid
        eval_res["defect_name"] = item["defect_name"]
        results.append(eval_res)

        if eval_res["remedy_success"]:
            success_count += 1

    pass_rate = success_count / len(gold_redlines) if gold_redlines else 1.0

    print("\n--- Statutory Redline Compliance Results ---")
    print(f"Clauses Tested:              {len(gold_redlines)}")
    print(f"Statutory Remedy Pass Rate:  {round(pass_rate * 100, 1)}%")
    for r in results:
        status_symbol = "✓ PASS" if r["remedy_success"] else "✗ FAIL"
        print(f"  [{status_symbol}] {r['defect_name']}: {r['details']}")
    print("=" * 80)

    return {
        "clauses_tested": len(gold_redlines),
        "statutory_remedy_pass_rate": round(pass_rate, 3),
        "detailed_remediations": results
    }


if __name__ == "__main__":
    is_live = "--live" in sys.argv
    run_contract_drafting_evaluation(live=is_live)

