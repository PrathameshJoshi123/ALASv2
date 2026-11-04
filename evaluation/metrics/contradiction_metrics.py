"""
Witness Statement Contradiction & Evidence Impeachment Metrics.

Implements evaluation standards for:
- Contradiction Identification Precision, Recall, and F1-score
- False Positive Rate (Spurious contradictions / hallucinated conflicts)
- Cohen's Kappa Inter-Annotator Agreement for legal practitioner blind reviews
"""

from typing import Any, Dict, List, Optional
import math


def compute_cohens_kappa(rater1_binary: List[int], rater2_binary: List[int]) -> float:
    """
    Compute Cohen's Kappa coefficient (κ) for inter-rater agreement between
    two independent legal practitioner reviews.
    
    κ = (p_o - p_e) / (1 - p_e)
    """
    assert len(rater1_binary) == len(rater2_binary), "Rater arrays must be of equal length"
    n = len(rater1_binary)
    if n == 0:
        return 1.0

    # Contingency table
    a = sum(1 for r1, r2 in zip(rater1_binary, rater2_binary) if r1 == 1 and r2 == 1)
    b = sum(1 for r1, r2 in zip(rater1_binary, rater2_binary) if r1 == 1 and r2 == 0)
    c = sum(1 for r1, r2 in zip(rater1_binary, rater2_binary) if r1 == 0 and r2 == 1)
    d = sum(1 for r1, r2 in zip(rater1_binary, rater2_binary) if r1 == 0 and r2 == 0)

    # Observed agreement
    p_o = (a + d) / n

    # Expected agreement by chance
    p_yes = ((a + b) / n) * ((a + c) / n)
    p_no = ((c + d) / n) * ((b + d) / n)
    p_e = p_yes + p_no

    if p_e >= 1.0:
        return 1.0

    kappa = (p_o - p_e) / (1.0 - p_e)
    return round(kappa, 3)


def evaluate_contradiction_detection(
    flagged_contradictions: List[Dict[str, Any]],
    gold_contradictions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluate detected witness contradictions against annotated gold contradictions.
    """
    if not flagged_contradictions and not gold_contradictions:
        return {
            "precision": 1.0,
            "recall": 1.0,
            "f1_score": 1.0,
            "false_positive_rate": 0.0,
            "flagged_count": 0,
            "gold_count": 0
        }

    # Match based on witness name & defect type
    matched_gold_indices = set()
    true_positives = 0
    false_positives = 0

    for flagged in flagged_contradictions:
        witness = flagged.get("witness_name", "").lower()
        defect = flagged.get("defect_type", "").lower()
        description = flagged.get("description", "").lower()

        matched = False
        for idx, gold in enumerate(gold_contradictions):
            if idx in matched_gold_indices:
                continue
            gold_witness = gold.get("witness_name", "").lower()
            gold_defect = gold.get("defect_type", "").lower()
            gold_desc = gold.get("description", "").lower()

            # Check overlap
            if (witness in gold_witness or gold_witness in witness) and (
                defect in gold_defect or gold_defect in defect
            ):
                matched = True
                matched_gold_indices.add(idx)
                break
            # Or description text keyword overlap
            desc_words = set(description.split())
            gold_words = set(gold_desc.split())
            if len(desc_words.intersection(gold_words)) >= 4:
                matched = True
                matched_gold_indices.add(idx)
                break

        if matched:
            true_positives += 1
        else:
            false_positives += 1

    false_negatives = len(gold_contradictions) - len(matched_gold_indices)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = false_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1, 3),
        "false_positive_rate": round(fpr, 3),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "flagged_count": len(flagged_contradictions),
        "gold_count": len(gold_contradictions),
    }

