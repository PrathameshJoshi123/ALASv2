r"""
LaTeX Paper Table Exporter & Inserter for ALAS.

Converts empirical evaluation metrics from 'evaluation_results_master.json'
into publication-ready LaTeX tables matching the exact schema in 'paper.tex':
- Table 1: RAG Evaluation Metrics using RAGAS Framework (\label{tab:rag_evaluation})
- Table 2: Performance of Clause Analysis Agent on Key Legal Clauses (\label{tab:clause_performance})
- Table 3: Performance of Case Document Classifier (\label{tab:doc_classification})

Can also output standalone LaTeX snippet or automatically update 'paper.tex'.
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAPER_PATH = PROJECT_ROOT / "paper.tex"
RESULTS_PATH = PROJECT_ROOT / "evaluation" / "evaluation_results_master.json"


def format_rag_table(rag_data: list) -> str:
    """Format LaTeX Table 1 for RAGAS evaluation."""
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{RAG Evaluation Metrics using RAGAS Framework}",
        r"\label{tab:rag_evaluation}",
        r"\begin{tabular}{lcccc}",
        r"\hline",
        r"\textbf{Model} & \textbf{Faithfulness} & \textbf{Answer Relevance} & \textbf{Context Precision} & \textbf{Context Recall} \\ \hline",
    ]
    for row in rag_data:
        model = row.get("model", "Model")
        f = f"{row.get('faithfulness', 0.0):.3f}"
        ar = f"{row.get('answer_relevance', 0.0):.3f}"
        cp = f"{row.get('context_precision', 0.0):.3f}"
        cr = f"{row.get('context_recall', 0.0):.3f}"
        lines.append(f"{model} & {f} & {ar} & {cp} & {cr} \\\\")
    lines.extend([
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
    ])
    return "\n".join(lines)


def format_clause_table(clause_metrics: dict) -> str:
    """Format LaTeX Table 2 for Clause Analysis."""
    per_class = clause_metrics.get("per_class", {})
    macro = clause_metrics.get("macro_avg", {})
    micro = clause_metrics.get("micro_avg", {})

    key_clauses = [
        "Limitation of Liability",
        "Indemnification",
        "Governing Law",
        "Dispute Resolution",
        "Force Majeure",
        "Confidentiality",
        "Intellectual Property",
        "Payment",
        "Termination",
    ]

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Performance of Clause Analysis Agent on Key Legal Clauses}",
        r"\label{tab:clause_performance}",
        r"\begin{tabular}{lccc}",
        r"\hline",
        r"\textbf{Clause Category} & \textbf{Precision} & \textbf{Recall} & \textbf{F1-score} \\ \hline",
    ]

    for k in key_clauses:
        metrics = per_class.get(k, {"precision": 0.0, "recall": 0.0, "f1_score": 0.0})
        p = f"{metrics.get('precision', 0.0):.3f}"
        r = f"{metrics.get('recall', 0.0):.3f}"
        f1 = f"{metrics.get('f1_score', 0.0):.3f}"
        lines.append(f"{k:<24} & {p} & {r} & {f1} \\\\")

    lines.append(r"\hline")
    mp = f"{macro.get('precision', 0.0):.3f}"
    mr = f"{macro.get('recall', 0.0):.3f}"
    mf1 = f"{macro.get('f1_score', 0.0):.3f}"
    lines.append(f"\\textbf{{Macro Average (22 classes)}} & {mp} & {mr} & {mf1} \\\\")

    up = f"{micro.get('precision', 0.0):.3f}"
    ur = f"{micro.get('recall', 0.0):.3f}"
    uf1 = f"{micro.get('f1_score', 0.0):.3f}"
    lines.append(f"\\textbf{{Micro Average (22 classes)}} & {up} & {ur} & {uf1} \\\\")

    lines.extend([
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
    ])
    return "\n".join(lines)


def format_doc_classification_table(doc_metrics: dict) -> str:
    """Format LaTeX Table 3 for Case Document Classifier."""
    per_class = doc_metrics.get("per_class", {})
    macro = doc_metrics.get("macro_avg", {})
    micro = doc_metrics.get("micro_avg", {})

    categories = [
        ("FIR", "FIR"),
        ("COURT_ORDER", "Court Order"),
        ("CHARGE_SHEET", "Charge Sheet"),
        ("WITNESS_STATEMENT", "Witness Statement"),
        ("FORENSIC_REPORT", "Forensic Report"),
        ("EVIDENCE_PHOTO", "Evidence Photo"),
        ("LEGAL_NOTICE", "Legal Notice"),
        ("PETITION_AFFIDAVIT", "Petition/Affidavit"),
        ("OTHER", "Other"),
    ]

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Performance of Case Document Classifier}",
        r"\label{tab:doc_classification}",
        r"\begin{tabular}{lccc}",
        r"\hline",
        r"\textbf{Document Category} & \textbf{Precision} & \textbf{Recall} & \textbf{F1-score} \\ \hline",
    ]

    for raw_cat, display_name in categories:
        metrics = per_class.get(raw_cat) or per_class.get(display_name, {"precision": 0.0, "recall": 0.0, "f1_score": 0.0})
        p = f"{metrics.get('precision', 0.0):.3f}"
        r = f"{metrics.get('recall', 0.0):.3f}"
        f1 = f"{metrics.get('f1_score', 0.0):.3f}"
        lines.append(f"{display_name:<24} & {p} & {r} & {f1} \\\\")

    lines.append(r"\hline")
    mp = f"{macro.get('precision', 0.0):.3f}"
    mr = f"{macro.get('recall', 0.0):.3f}"
    mf1 = f"{macro.get('f1_score', 0.0):.3f}"
    lines.append(f"\\textbf{{Macro Average}}     & {mp} & {mr} & {mf1} \\\\")

    up = f"{micro.get('precision', 0.0):.3f}"
    ur = f"{micro.get('recall', 0.0):.3f}"
    uf1 = f"{micro.get('f1_score', 0.0):.3f}"
    lines.append(f"\\textbf{{Micro Average}}     & {up} & {ur} & {uf1} \\\\")

    lines.extend([
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
    ])
    return "\n".join(lines)


def update_paper_tex(results: dict, paper_file: Path = PAPER_PATH):
    """Replace tables in paper.tex with newly formatted real empirical tables."""
    if not paper_file.exists():
        print(f"Error: {paper_file} not found.")
        return

    with open(paper_file, "r", encoding="utf-8") as f:
        content = f.read()

    modules = results.get("modules", {})

    # 1. Update RAG table
    rag_data = modules.get("jurist_rag", {}).get("rag_model_evaluations", [])
    if rag_data:
        rag_table_tex = format_rag_table(rag_data)
        content = re.sub(
            r"\\begin\{table\}\[htbp\]\s*\\centering\s*\\caption\{RAG Evaluation Metrics using RAGAS Framework\}.*?\\end\{table\}",
            rag_table_tex,
            content,
            flags=re.DOTALL
        )

    # 2. Update Clause table
    clause_data = modules.get("clause_classification", {})
    if clause_data:
        clause_table_tex = format_clause_table(clause_data)
        content = re.sub(
            r"\\begin\{table\}\[htbp\]\s*\\centering\s*\\caption\{Performance of Clause Analysis Agent on Key Legal Clauses\}.*?\\end\{table\}",
            clause_table_tex,
            content,
            flags=re.DOTALL
        )

    # 3. Update Doc classification table
    doc_data = modules.get("case_document_classification", {})
    if doc_data:
        doc_table_tex = format_doc_classification_table(doc_data)
        content = re.sub(
            r"\\begin\{table\}\[htbp\]\s*\\centering\s*\\caption\{Performance of Case Document Classifier\}.*?\\end\{table\}",
            doc_table_tex,
            content,
            flags=re.DOTALL
        )

    with open(paper_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✓ Successfully updated {paper_file.name} with live benchmark tables!")


def main():
    parser = argparse.ArgumentParser(description="Export Benchmark Results to LaTeX Tables")
    parser.add_argument("--results", type=str, default=str(RESULTS_PATH), help="Path to evaluation_results_master.json")
    parser.add_argument("--update-paper", action="store_true", help="Directly update paper.tex with new tables")
    parser.add_argument("--print-only", action="store_true", help="Print LaTeX table code to console")
    args = parser.parse_args()

    results_file = Path(args.results)
    if not results_file.exists():
        print(f"Results file '{results_file}' not found. Please run 'run_all_evaluations.py' first.")
        return

    with open(results_file, "r", encoding="utf-8") as f:
        results = json.load(f)

    modules = results.get("modules", {})
    rag_table = format_rag_table(modules.get("jurist_rag", {}).get("rag_model_evaluations", []))
    clause_table = format_clause_table(modules.get("clause_classification", {}))
    doc_table = format_doc_classification_table(modules.get("case_document_classification", {}))

    snippet = f"% === ALAS BENCHMARK RESULTS ===\n\n{rag_table}\n\n{clause_table}\n\n{doc_table}\n"

    if args.print_only or not args.update_paper:
        print(snippet)

    if args.update_paper:
        update_paper_tex(results)


if __name__ == "__main__":
    main()
