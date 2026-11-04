"""
RAGAS (Retrieval Augmented Generation Assessment) Metrics Suite.

Implements the 4 foundational metrics defined in Es et al. (2023)
"Ragas: Automated Evaluation of Retrieval Augmented Generation":
1. Faithfulness (Grounding of generated answer in retrieved chunks)
2. Answer Relevance (Alignment of generated answer with the legal query)
3. Context Precision (Signal-to-noise ratio in retrieved context chunks)
4. Context Recall (Coverage of ground-truth facts by retrieved context)
"""

from typing import Any, Dict, List, Optional
import re
from collections import Counter


def compute_lexical_similarity(text_a: str, text_b: str) -> float:
    """Compute token-level Jaccard similarity between two texts."""
    tokens_a = set(re.findall(r"\w+", text_a.lower()))
    tokens_b = set(re.findall(r"\w+", text_b.lower()))
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union)


def compute_context_precision(retrieved_contexts: List[str], ground_truth_facts: List[str]) -> float:
    """
    Context Precision: Evaluates whether relevant chunks are ranked higher in the retrieved results.
    Precision@k = (relevant chunks up to rank k) / k
    """
    if not retrieved_contexts:
        return 0.0
    if not ground_truth_facts:
        return 1.0

    hits = []
    for ctx in retrieved_contexts:
        ctx_lower = ctx.lower()
        is_relevant = any(
            fact.lower() in ctx_lower or compute_lexical_similarity(fact, ctx) > 0.35
            for fact in ground_truth_facts
        )
        hits.append(1 if is_relevant else 0)

    total_relevant = sum(hits)
    if total_relevant == 0:
        return 0.0

    score = 0.0
    running_hits = 0
    for k, hit in enumerate(hits, start=1):
        if hit == 1:
            running_hits += 1
            precision_at_k = running_hits / k
            score += precision_at_k

    return round(score / total_relevant, 3)


def compute_context_recall(retrieved_contexts: List[str], ground_truth_facts: List[str]) -> float:
    """
    Context Recall: Proportion of ground-truth facts present in retrieved chunks.
    """
    if not ground_truth_facts:
        return 1.0
    if not retrieved_contexts:
        return 0.0

    joined_context = " ".join(retrieved_contexts).lower()
    covered = 0
    for fact in ground_truth_facts:
        fact_words = [w for w in re.findall(r"\w+", fact.lower()) if len(w) > 3]
        if not fact_words:
            covered += 1
            continue
        matches = sum(1 for w in fact_words if w in joined_context)
        if (matches / len(fact_words)) >= 0.65:
            covered += 1

    return round(covered / len(ground_truth_facts), 3)


def compute_faithfulness_heuristic(answer: str, retrieved_contexts: List[str]) -> float:
    """
    Heuristic Faithfulness: Measures sentence-level grounding of answer against context.
    For production LLM-based evaluation, evaluate_faithfulness_llm is used.
    """
    if not answer or not answer.strip():
        return 0.0
    if not retrieved_contexts:
        return 0.0

    sentences = [s.strip() for s in re.split(r"[.!?\n]", answer) if len(s.strip().split()) > 3]
    if not sentences:
        return 1.0

    joined_context = " ".join(retrieved_contexts).lower()
    supported = 0
    for s in sentences:
        words = [w for w in re.findall(r"\w+", s.lower()) if len(w) > 3]
        if not words:
            supported += 1
            continue
        matches = sum(1 for w in words if w in joined_context)
        if (matches / len(words)) >= 0.60:
            supported += 1

    return round(supported / len(sentences), 3)


def compute_answer_relevance_heuristic(question: str, answer: str) -> float:
    """
    Heuristic Answer Relevance: Measures keyword and semantic coverage between question and answer.
    """
    if not answer or not answer.strip():
        return 0.0
    q_words = [w for w in re.findall(r"\w+", question.lower()) if len(w) > 3]
    if not q_words:
        return 1.0
    ans_lower = answer.lower()
    matches = sum(1 for w in q_words if w in ans_lower)
    overlap_ratio = matches / len(q_words)
    # Scale with penalty for answers that are excessively short or trivial
    length_penalty = min(1.0, len(answer.split()) / 25.0)
    return round(min(1.0, 0.4 + 0.6 * overlap_ratio) * length_penalty, 3)


def evaluate_ragas_instance(
    question: str,
    answer: str,
    retrieved_contexts: List[str],
    ground_truth_facts: List[str],
    evaluator_llm: Optional[Any] = None
) -> Dict[str, float]:
    """
    Evaluate a single QA instance across all 4 RAGAS metrics.
    If evaluator_llm is provided, uses LLM-as-a-judge for faithfulness and relevance;
    otherwise uses robust heuristic fallback.
    """
    if evaluator_llm is not None:
        try:
            return evaluate_ragas_llm(evaluator_llm, question, answer, retrieved_contexts, ground_truth_facts)
        except Exception:
            pass

    return {
        "faithfulness": compute_faithfulness_heuristic(answer, retrieved_contexts),
        "answer_relevance": compute_answer_relevance_heuristic(question, answer),
        "context_precision": compute_context_precision(retrieved_contexts, ground_truth_facts),
        "context_recall": compute_context_recall(retrieved_contexts, ground_truth_facts),
    }


def evaluate_ragas_llm(
    llm: Any,
    question: str,
    answer: str,
    retrieved_contexts: List[str],
    ground_truth_facts: List[str]
) -> Dict[str, float]:
    """
    LLM-as-a-judge prompt evaluation for RAGAS faithfulness and relevance.
    """
    from langchain_core.messages import HumanMessage
    import json

    context_str = "\n---\n".join(retrieved_contexts[:5])
    prompt = f"""You are an expert legal AI evaluator following the Ragas benchmark methodology.
Evaluate the following legal Q&A generation:

[LEGAL QUERY]:
{question}

[RETRIEVED CONTEXT]:
{context_str[:6000]}

[GENERATED ANSWER]:
{answer}

[GROUND TRUTH FACTS]:
{json.dumps(ground_truth_facts, indent=2)}

Score each of the following 4 metrics between 0.00 and 1.00:
1. "faithfulness": Ratio of claims in generated answer that are directly supported by the retrieved context. (No hallucination = 1.0)
2. "answer_relevance": How directly and concisely the answer addresses the legal query.
3. "context_precision": Ratio of relevant chunks in retrieved context.
4. "context_recall": Ratio of ground truth facts captured in the retrieved context.

Return ONLY a valid JSON object matching:
{{
  "faithfulness": 0.95,
  "answer_relevance": 0.92,
  "context_precision": 0.88,
  "context_recall": 0.90
}}
"""
    resp = llm.invoke([HumanMessage(content=prompt)])
    content = resp.content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    data = json.loads(content)
    return {
        "faithfulness": float(data.get("faithfulness", 0.0)),
        "answer_relevance": float(data.get("answer_relevance", 0.0)),
        "context_precision": float(data.get("context_precision", 0.0)),
        "context_recall": float(data.get("context_recall", 0.0)),
    }

