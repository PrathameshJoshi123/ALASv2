"""
Temporal Timeline and Chronological Integrity Metrics.

Implements evaluation standards for:
- Timeline Event Date Extraction (Jaccard Similarity)
- Temporal Sequence Ordering (Kendall's Tau rank correlation)
- Event-Date Alignment Precision, Recall, and F1-score
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import re
from datetime import datetime


def normalize_date_str(date_str: str) -> Optional[str]:
    """Normalize diverse date strings into ISO format YYYY-MM-DD."""
    if not date_str:
        return None
    s = str(date_str).strip()
    
    # Try YYYY-MM-DD
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        try:
            return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        except Exception:
            pass

    # Try DD/MM/YYYY or DD-MM-YYYY
    m2 = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s)
    if m2:
        try:
            return f"{int(m2.group(3)):04d}-{int(m2.group(2)):02d}-{int(m2.group(1)):02d}"
        except Exception:
            pass

    return s[:10]


def compute_date_jaccard_similarity(pred_dates: List[str], gold_dates: List[str]) -> float:
    """
    Compute Jaccard similarity between extracted timeline dates and gold-standard dates:
    J(A, B) = |A ∩ B| / |A ∪ B|
    """
    set_pred = set(filter(None, [normalize_date_str(d) for d in pred_dates]))
    set_gold = set(filter(None, [normalize_date_str(d) for d in gold_dates]))

    if not set_pred and not set_gold:
        return 1.0
    if not set_pred or not set_gold:
        return 0.0

    intersection = set_pred.intersection(set_gold)
    union = set_pred.union(set_gold)
    return round(len(intersection) / len(union), 4)


def compute_kendall_tau(pred_order: List[Any], gold_order: List[Any]) -> float:
    """
    Compute Kendall's Tau rank correlation coefficient to measure chronological sequence integrity.
    Range: [-1.0, 1.0], where 1.0 indicates perfect chronological order.
    """
    common_items = [item for item in gold_order if item in pred_order]
    n = len(common_items)
    if n < 2:
        return 1.0

    pred_ranks = {item: idx for idx, item in enumerate(pred_order)}
    concordant = 0
    discordant = 0

    for i in range(n):
        for j in range(i + 1, n):
            item_a = common_items[i]
            item_b = common_items[j]
            # In gold, item_a comes before item_b
            if pred_ranks[item_a] < pred_ranks[item_b]:
                concordant += 1
            elif pred_ranks[item_a] > pred_ranks[item_b]:
                discordant += 1

    total_pairs = (n * (n - 1)) / 2
    if total_pairs == 0:
        return 1.0
    tau = (concordant - discordant) / total_pairs
    return round(tau, 4)


def evaluate_timeline_instance(
    extracted_timeline: List[Dict[str, Any]],
    gold_timeline: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluate an extracted timeline against gold-standard milestones.
    """
    pred_dates = [e.get("event_date") or e.get("date") for e in extracted_timeline]
    gold_dates = [e.get("event_date") or e.get("date") for e in gold_timeline]

    jaccard = compute_date_jaccard_similarity(pred_dates, gold_dates)
    
    # Event matching
    norm_gold_dates = [normalize_date_str(d) for d in gold_dates]
    norm_pred_dates = [normalize_date_str(d) for d in pred_dates]
    
    tp = sum(1 for d in norm_pred_dates if d in norm_gold_dates)
    fp = sum(1 for d in norm_pred_dates if d not in norm_gold_dates)
    fn = sum(1 for d in norm_gold_dates if d not in norm_pred_dates)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    tau = compute_kendall_tau(norm_pred_dates, norm_gold_dates)

    return {
        "jaccard_similarity": round(jaccard, 4),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1, 3),
        "kendall_tau": round(tau, 3),
        "extracted_count": len(extracted_timeline),
        "gold_count": len(gold_timeline),
    }
