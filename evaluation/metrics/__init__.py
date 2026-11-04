"""
Legal AI Evaluation Metrics Package.
"""

from evaluation.metrics.classification_metrics import (
    compute_token_overlap_f1,
    compute_multiclass_metrics,
)
from evaluation.metrics.ragas_metrics import (
    evaluate_ragas_instance,
    compute_context_precision,
    compute_context_recall,
    compute_faithfulness_heuristic,
    compute_answer_relevance_heuristic,
)
from evaluation.metrics.temporal_metrics import (
    compute_date_jaccard_similarity,
    compute_kendall_tau,
    evaluate_timeline_instance,
    normalize_date_str,
)
from evaluation.metrics.contradiction_metrics import (
    compute_cohens_kappa,
    evaluate_contradiction_detection,
)
from evaluation.metrics.statutory_compliance_metrics import (
    evaluate_statutory_remediation,
    compute_kanoon_citation_authenticity,
)
from evaluation.metrics.system_latency_metrics import (
    compute_latency_percentiles,
    compute_throughput,
)

__all__ = [
    "compute_token_overlap_f1",
    "compute_multiclass_metrics",
    "evaluate_ragas_instance",
    "compute_context_precision",
    "compute_context_recall",
    "compute_faithfulness_heuristic",
    "compute_answer_relevance_heuristic",
    "compute_date_jaccard_similarity",
    "compute_kendall_tau",
    "evaluate_timeline_instance",
    "normalize_date_str",
    "compute_cohens_kappa",
    "evaluate_contradiction_detection",
    "evaluate_statutory_remediation",
    "compute_kanoon_citation_authenticity",
    "compute_latency_percentiles",
    "compute_throughput",
]

