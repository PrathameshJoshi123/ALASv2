"""
Classification and Extraction Metrics for Legal Benchmark Evaluation.

Implements academic standard evaluation metrics matching:
- CUAD (Contract Understanding Atticus Dataset)
- LexGLUE (Legal General Language Understanding Evaluation)
- ILDC (Indian Legal Documents Corpus)
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import math


def compute_token_overlap_f1(predicted_text: str, gold_text: str) -> float:
    """
    Compute word/token-level overlap F1 score (CUAD / SQuAD evaluation standard).
    """
    pred_tokens = predicted_text.strip().lower().split()
    gold_tokens = gold_text.strip().lower().split()
    
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0
        
    common = defaultdict(int)
    for t in pred_tokens:
        common[t] += 1
        
    overlap_count = 0
    gold_counts = defaultdict(int)
    for t in gold_tokens:
        gold_counts[t] += 1
        
    for token, count in gold_counts.items():
        overlap_count += min(count, common.get(token, 0))
        
    if overlap_count == 0:
        return 0.0
        
    precision = overlap_count / len(pred_tokens)
    recall = overlap_count / len(gold_tokens)
    return 2.0 * (precision * recall) / (precision + recall)


def compute_multiclass_metrics(
    y_true: List[str], 
    y_pred: List[str], 
    labels: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compute Precision, Recall, and F1-score for each class as well as
    Macro Average, Micro Average, and Overall Accuracy.
    
    Standard formulas:
      Precision = TP / (TP + FP)
      Recall    = TP / (TP + FN)
      F1-score  = 2 * (Precision * Recall) / (Precision + Recall)
    """
    assert len(y_true) == len(y_pred), "y_true and y_pred must have equal length"
    
    if labels is None:
        labels = sorted(list(set(y_true) | set(y_pred)))
        
    counts = {label: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for label in labels}
    
    total_correct = 0
    for true_val, pred_val in zip(y_true, y_pred):
        if true_val == pred_val:
            total_correct += 1
            if pred_val in counts:
                counts[pred_val]["tp"] += 1
        else:
            if pred_val in counts:
                counts[pred_val]["fp"] += 1
            if true_val in counts:
                counts[true_val]["fn"] += 1
                
        if true_val in counts:
            counts[true_val]["support"] += 1

    per_class_results = {}
    macro_p = 0.0
    macro_r = 0.0
    macro_f1 = 0.0
    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_support = len(y_true)

    for label in labels:
        tp = counts[label]["tp"]
        fp = counts[label]["fp"]
        fn = counts[label]["fn"]
        support = counts[label]["support"]

        total_tp += tp
        total_fp += fp
        total_fn += fn

        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (p * r) / (p + r) if (p + r) > 0 else 0.0

        per_class_results[label] = {
            "precision": round(p, 3),
            "recall": round(r, 3),
            "f1_score": round(f1, 3),
            "support": support,
        }
        macro_p += p
        macro_r += r
        macro_f1 += f1

    num_classes = len(labels) if len(labels) > 0 else 1
    macro_precision = macro_p / num_classes
    macro_recall = macro_r / num_classes
    macro_f1_score = macro_f1 / num_classes

    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1_score = (
        2 * (micro_precision * micro_recall) / (micro_precision + micro_recall)
        if (micro_precision + micro_recall) > 0
        else 0.0
    )

    accuracy = total_correct / total_support if total_support > 0 else 0.0

    return {
        "per_class": per_class_results,
        "macro_avg": {
            "precision": round(macro_precision, 3),
            "recall": round(macro_recall, 3),
            "f1_score": round(macro_f1_score, 3),
        },
        "micro_avg": {
            "precision": round(micro_precision, 3),
            "recall": round(micro_recall, 3),
            "f1_score": round(micro_f1_score, 3),
        },
        "accuracy": round(accuracy, 3),
        "total_samples": total_support,
    }

