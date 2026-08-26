"""
Celery tasks for PDF processing.
Handles background processing of PDF contracts using Unstructured library.
"""

import json
import logging
from pathlib import Path
from typing import Any

from celery import chain

from backend.celery_app import celery_app
from celery.utils.log import get_task_logger

from langchain_core.messages import HumanMessage
from backend.services.pdf_service import PDFService

logger = get_task_logger(__name__)

# Initialize PDF service for background tasks
pdf_service = PDFService(
    strategy="fast",  # Let Unstructured choose the best strategy
    infer_table_structure=False,
    include_page_breaks=True,
    languages=["eng"],  # Default to English, can be overridden per task
)


@celery_app.task(bind=True, name="process_pdf_task")
def process_pdf_task(
    self,
    document_id: str,
    file_path: str,
    filename: str,
) -> dict[str, Any]:
    """
    Background task to process a PDF contract.
    
    Extracts structured elements from the PDF using Unstructured:
    - Titles
    - Paragraphs (NarrativeText)
    - Tables
    - Other document elements
    
    Args:
        document_id: Unique identifier for the document
        file_path: Path to the PDF file
        filename: Original filename of the document
        
    Returns:
        Dictionary with processing results:
        {
            "status": "success" or "error",
            "document_id": str,
            "elements_count": int,
            "elements": list of element dicts,
            "error": str (if error)
        }
    """
    try:
        logger.info(f"Starting PDF processing for document: {document_id}")
        
        # Verify file exists
        storage_path = Path(file_path)
        if not storage_path.exists():
            error_msg = f"PDF file not found: {file_path}"
            logger.error(error_msg)
            # Save error to output folder
            output_dir = Path("backend/storage/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{document_id}_error.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({"status": "error", "document_id": document_id, "error": error_msg}, f, indent=2)
            return {
                "status": "error",
                "document_id": document_id,
                "error": error_msg,
                "output_file": str(output_file),
            }
        
        # Process PDF
        elements = pdf_service.process_pdf(
            file_path=storage_path,
            filename=filename,
        )
        
        logger.info(f"Processed document {document_id}: extracted {len(elements)} elements")
        
        # Save output to file in output folder
        output_dir = Path("backend/storage/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{document_id}.json"
        
        output_data = {
            "status": "success",
            "document_id": document_id,
            "filename": filename,
            "elements_count": len(elements),
            "elements": elements,
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved output to: {output_file}")
        
        return {
            "status": "success",
            "document_id": document_id,
            "elements_count": len(elements),
            "elements": elements,
            "output_file": str(output_file),
        }
        
    except ImportError as e:
        error_msg = f"Unstructured library not available: {e}"
        logger.error(error_msg)
        # Save error to output folder
        output_dir = Path("backend/storage/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{document_id}_error.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"status": "error", "document_id": document_id, "error": error_msg}, f, indent=2)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
            "output_file": str(output_file),
        }
    except Exception as e:
        error_msg = f"Failed to process PDF: {e}"
        logger.error(f"Error processing document {document_id}: {e}")
        # Save error to output folder
        output_dir = Path("backend/storage/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{document_id}_error.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"status": "error", "document_id": document_id, "error": error_msg}, f, indent=2)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
            "output_file": str(output_file),
        }


@celery_app.task(bind=True, name="process_and_chunk_task")
def process_and_chunk_task(
    self,
    document_id: str,
    file_path: str,
    filename: str,
) -> dict[str, Any]:
    """
    Background task to process PDF AND automatically chunk it using Celery chain.
    
    This task chains PDF processing with automatic chunking:
    1. process_pdf_task extracts elements
    2. chunk_document_task processes elements into chunks
    
    Args:
        document_id: Unique identifier for the document
        file_path: Path to the PDF file
        filename: Original filename of the document
        
    Returns:
        Dictionary with combined results from both tasks
    """
    try:
        from backend.tasks.chunking_tasks import chunk_document_task
        
        logger.info(f"Starting chained PDF processing + chunking for document: {document_id}")
        
        # Create the chain: PDF processing -> Chunking
        # The result of process_pdf_task is passed to chunk_document_task
        # But chunk_document_task expects (document_id, elements, filename)
        # So we need to use a helper function or modify the chain
        
        # For now, we'll call them sequentially to maintain simplicity
        # Celery chains with complex argument passing require signature manipulation
        
        # Step 1: Process PDF
        pdf_result = process_pdf_task(document_id, file_path, filename)
        
        if pdf_result.get("status") != "success":
            return {
                **pdf_result,
                "chunking": {"status": "skipped", "reason": "PDF processing failed"},
            }
        
        # Step 2: Chunk the elements
        elements = pdf_result.get("elements", [])
        chunk_result = chunk_document_task(document_id, elements, filename)
        
        # Step 3: Run Orchestrator Agent to perform complete contract analysis
        agent_analysis = None
        if chunk_result.get("status") == "success":
            try:
                logger.info(f"Triggering Orchestrator agent contract analysis for document: {document_id}")
                from backend.agents.orchestrator_agent import create_contract_orchestrator
                
                # Instantiate and invoke orchestrator agent
                orchestrator = create_contract_orchestrator()
                
                # The orchestrator uses the database tools to pull context sequentially
                agent_msg = f"Analyze the contract with document ID: {document_id}"
                
                # Call orchestrator.stream to log progress in real-time
                # Establish logging directories and file
                log_dir = Path("backend/storage/logs")
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file_path = log_dir / f"{document_id}_agent_execution.log"
                
                with open(log_file_path, "w", encoding="utf-8") as log_file:
                    def log_write(text: str):
                        logger.info(text)
                        print(text)
                        log_file.write(text + "\n")
                        log_file.flush()
                        
                    log_write("="*80)
                    log_write(f">>> STARTING DEEP AGENT CONTRACT ANALYSIS FOR DOCUMENT: {document_id}")
                    log_write(f">>> Log file: {log_file_path}")
                    log_write("="*80 + "\n")
                    
                    # Stream updates from the coordinator and all subgraphs
                    for chunk in orchestrator.stream(
                        {"messages": [HumanMessage(content=agent_msg)]},
                        stream_mode="updates",
                        subgraphs=True,
                        version="v2",
                    ):
                        if not isinstance(chunk, dict) or "type" not in chunk:
                            continue
                            
                        if chunk["type"] == "updates":
                            ns = chunk.get("ns", [])
                            data = chunk.get("data", {})
                            
                            # Subagent namespace identifies the active subagent
                            if ns:
                                subagent_name = ns[0]
                                path_str = " -> ".join(ns)
                                log_write(f"\n[Subagent: {path_str}] running node...")
                                for node_name, node_data in data.items():
                                    log_write(f"  └─ Step: {node_name}")
                                    # Print messages / tool calls inside subagents
                                    if isinstance(node_data, dict) and "messages" in node_data:
                                        for msg in node_data["messages"]:
                                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                                for tc in msg.tool_calls:
                                                    log_write(f"     └─ Tool Call: {tc.get('name')}")
                                                    log_write(f"        Arguments: {json.dumps(tc.get('args'))}")
                                            elif msg.type == "tool":
                                                log_write(f"     └─ Tool '{msg.name}' Response snippet: {str(msg.content)[:300]}...")
                                            elif msg.type == "ai" and msg.content:
                                                log_write(f"     └─ AI Response snippet: {str(msg.content)[:200]}...")
                            else:
                                log_write("\n[Main Coordinator Agent] running node...")
                                for node_name, node_data in data.items():
                                    log_write(f"  └─ Step: {node_name}")
                                    
                                    # Accumulate/extract final structured response from the coordinator nodes
                                    if isinstance(node_data, dict):
                                        if "structured_response" in node_data and node_data["structured_response"] is not None:
                                            agent_analysis = node_data["structured_response"]
                                        elif "response" in node_data and node_data["response"] is not None:
                                            agent_analysis = node_data["response"]
                                            
                                    # Look for subagent completion tool message
                                    if node_name == "tools" and isinstance(node_data, dict) and "messages" in node_data:
                                        for msg in node_data["messages"]:
                                            if msg.type == "tool" and msg.name == "task":
                                                log_write(f"\n>>> Subagent execution completed: {msg.name}")
                                                log_write(f"    Result snippet: {str(msg.content)[:300]}...")
                    
                    log_write("\n" + "="*80)
                    log_write(">>> DEEP AGENT CONTRACT ANALYSIS COMPLETE")
                    log_write("="*80 + "\n")
                
                logger.info(f"Orchestrator contract analysis completed for document: {document_id}")
            except Exception as orchestrator_err:
                logger.error(f"Failed orchestrator analysis in chained processing: {orchestrator_err}", exc_info=True)
                agent_analysis = {"status": "error", "error": str(orchestrator_err)}
        
        # Save only the orchestrator agent analysis report in the storage outputs folder
        if agent_analysis:
            try:
                output_dir = Path("backend/storage/outputs")
                output_dir.mkdir(parents=True, exist_ok=True)
                report_file = output_dir / f"{document_id}_analysis_report.json"
                
                # Serialize Pydantic model to dict or dump JSON directly
                if hasattr(agent_analysis, "model_dump"):
                    report_data = agent_analysis.model_dump()
                else:
                    report_data = agent_analysis
                
                with open(report_file, "w", encoding="utf-8") as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved agent analysis report to: {report_file}")
                
                # Save to database
                from backend.services.contract_analysis_service import save_contract_analysis_to_db
                db_result = save_contract_analysis_to_db(document_id, report_data, overwrite=True)
                logger.info(f"DB Save result for document {document_id}: {db_result}")
                
                return {
                    "status": "success",
                    "document_id": document_id,
                    "analysis_report_file": str(report_file),
                    "analysis": report_data
                }
            except Exception as report_err:
                logger.error(f"Failed to save agent analysis report: {report_err}", exc_info=True)

        return {
            "status": "error",
            "document_id": document_id,
            "error": "Agent analysis was not generated or could not be saved."
        }
        
    except Exception as e:
        error_msg = f"Failed in chained processing: {e}"
        logger.error(f"Error in chained task for document {document_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
        }


@celery_app.task(bind=True, name="run_agent_analysis_task")
def run_agent_analysis_task(
    self,
    document_id: str,
) -> dict[str, Any]:
    """
    Background task to run Orchestrator agent contract analysis ONLY.
    
    Args:
        document_id: Unique identifier for the document
        
    Returns:
        Dictionary with analysis results
    """
    try:
        logger.info(f"Triggering Orchestrator agent contract analysis only for document: {document_id}")
        from backend.agents.orchestrator_agent import create_contract_orchestrator
        
        # Instantiate and invoke orchestrator agent
        orchestrator = create_contract_orchestrator()
        
        # The orchestrator uses the database tools to pull context sequentially
        agent_msg = f"Analyze the contract with document ID: {document_id}"
        
        agent_analysis = None
        
        # Establish logging directories and file
        log_dir = Path("backend/storage/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / f"{document_id}_agent_execution.log"
        
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            def log_write(text: str):
                logger.info(text)
                print(text)
                log_file.write(text + "\n")
                log_file.flush()
                
            log_write("="*80)
            log_write(f">>> STARTING DEEP AGENT CONTRACT ANALYSIS (AGENT-ONLY) FOR DOCUMENT: {document_id}")
            log_write(f">>> Log file: {log_file_path}")
            log_write("="*80 + "\n")
            
            # Stream updates from the coordinator and all subgraphs
            for chunk in orchestrator.stream(
                {"messages": [HumanMessage(content=agent_msg)]},
                stream_mode="updates",
                subgraphs=True,
                version="v2",
            ):
                if not isinstance(chunk, dict) or "type" not in chunk:
                    continue
                    
                if chunk["type"] == "updates":
                    ns = chunk.get("ns", [])
                    data = chunk.get("data", {})
                    
                    # Subagent namespace identifies the active subagent
                    if ns:
                        subagent_name = ns[0]
                        path_str = " -> ".join(ns)
                        log_write(f"\n[Subagent: {path_str}] running node...")
                        for node_name, node_data in data.items():
                            log_write(f"  └─ Step: {node_name}")
                            # Print messages / tool calls inside subagents
                            if isinstance(node_data, dict) and "messages" in node_data:
                                for msg in node_data["messages"]:
                                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                                        for tc in msg.tool_calls:
                                            log_write(f"     └─ Tool Call: {tc.get('name')}")
                                            log_write(f"        Arguments: {json.dumps(tc.get('args'))}")
                                    elif msg.type == "tool":
                                        log_write(f"     └─ Tool '{msg.name}' Response snippet: {str(msg.content)[:300]}...")
                                    elif msg.type == "ai" and msg.content:
                                        log_write(f"     └─ AI Response snippet: {str(msg.content)[:200]}...")
                    else:
                        log_write("\n[Main Coordinator Agent] running node...")
                        for node_name, node_data in data.items():
                            log_write(f"  └─ Step: {node_name}")
                            
                            # Accumulate/extract final structured response from the coordinator nodes
                            if isinstance(node_data, dict):
                                if "structured_response" in node_data and node_data["structured_response"] is not None:
                                    agent_analysis = node_data["structured_response"]
                                elif "response" in node_data and node_data["response"] is not None:
                                    agent_analysis = node_data["response"]
                                    
                            # Look for subagent completion tool message
                            if node_name == "tools" and isinstance(node_data, dict) and "messages" in node_data:
                                for msg in node_data["messages"]:
                                    if msg.type == "tool" and msg.name == "task":
                                        log_write(f"\n>>> Subagent execution completed: {msg.name}")
                                        log_write(f"    Result snippet: {str(msg.content)[:300]}...")
            
            log_write("\n" + "="*80)
            log_write(">>> DEEP AGENT CONTRACT ANALYSIS COMPLETE")
            log_write("="*80 + "\n")
        
        logger.info(f"Orchestrator contract analysis completed for document: {document_id}")
        
        # Save only the orchestrator agent analysis report in the storage outputs folder
        if agent_analysis:
            try:
                output_dir = Path("backend/storage/outputs")
                output_dir.mkdir(parents=True, exist_ok=True)
                report_file = output_dir / f"{document_id}_analysis_report.json"
                
                # Serialize Pydantic model to dict or dump JSON directly
                if hasattr(agent_analysis, "model_dump"):
                    report_data = agent_analysis.model_dump()
                else:
                    report_data = agent_analysis
                
                with open(report_file, "w", encoding="utf-8") as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved agent analysis report to: {report_file}")
                
                # Save to database
                from backend.services.contract_analysis_service import save_contract_analysis_to_db
                db_result = save_contract_analysis_to_db(document_id, report_data, overwrite=True)
                logger.info(f"DB Save result for document {document_id}: {db_result}")
                
                return {
                    "status": "success",
                    "document_id": document_id,
                    "analysis_report_file": str(report_file),
                    "analysis": report_data
                }
            except Exception as report_err:
                logger.error(f"Failed to save agent analysis report: {report_err}", exc_info=True)
        
        return {
            "status": "error",
            "document_id": document_id,
            "error": "Agent analysis was not generated or could not be saved."
        }
        
    except Exception as e:
        error_msg = f"Failed in agent analysis task: {e}"
        logger.error(f"Error in agent analysis task for document {document_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg,
        }


__all__ = ["process_pdf_task", "process_and_chunk_task", "run_agent_analysis_task"]
