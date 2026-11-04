"""
Evaluation Runners Package.
"""

from evaluation.runners.eval_clause_extraction import run_clause_evaluation
from evaluation.runners.eval_case_classification import run_case_classification_evaluation
from evaluation.runners.eval_jurist_rag import run_rag_evaluation
from evaluation.runners.eval_timeline_and_witness import run_timeline_and_witness_evaluation
from evaluation.runners.eval_contract_drafting import run_contract_drafting_evaluation
from evaluation.runners.eval_trial_debate import run_trial_debate_evaluation

__all__ = [
    "run_clause_evaluation",
    "run_case_classification_evaluation",
    "run_rag_evaluation",
    "run_timeline_and_witness_evaluation",
    "run_contract_drafting_evaluation",
    "run_trial_debate_evaluation",
]

