import json
import logging
from pathlib import Path
from typing import Any

from celery import chain
from backend.celery_app import celery_app
from celery.utils.log import get_task_logger

from langchain_core.messages import HumanMessage
from backend.utils.llm_utils import execute_with_exponential_backoff
from backend.database import SessionLocal
from backend.models.documents import Document
from backend.services.chunking.database import Chunk
from sqlalchemy import select, func

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="run_agent_drafting_task")
def run_agent_drafting_task(
    self,
    document_id: str,
    drafting_instructions: str,
    contract_type: str | None = None,
    company_name: str | None = None,
    counterparty_name: str | None = None,
    favor_party: str | None = "Balanced",
    governing_law: str | None = "Indian Contract Act, 1872",
    drafting_style: str | None = "Institutional Legal",
    auto_chunk: bool = True,
) -> dict[str, Any]:
    """
    Background task to run the Contract Drafting Orchestrator agent.
    If the template document chunks are missing from the database,
    it automatically processes and chunks the PDF document first (if auto_chunk is True).
    """
    try:
        logger.info(f"Starting contract drafting for document template: {document_id}")
        
        file_path = None
        filename = None
        
        # 1. Check document and chunk existence in DB
        with SessionLocal() as db:
            result = db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                error_msg = f"Template document with ID {document_id} not found in database"
                logger.error(error_msg)
                return {"status": "error", "error": error_msg}
                
            file_path = document.storage_link
            filename = document.name
            
            # Check chunks count
            chunks_count = db.execute(
                select(func.count(Chunk.chunk_id)).where(Chunk.document_id == document_id)
            ).scalar() or 0
            
        # 2. Trigger auto-processing if chunks are 0 and template file exists
        if chunks_count == 0:
            if file_path and Path(file_path).exists():
                if not auto_chunk:
                    error_msg = f"Chunks count is 0 for template {document_id} and auto_chunk is disabled."
                    logger.error(error_msg)
                    return {"status": "error", "error": error_msg}
                    
                logger.info(f"Chunks count is 0 for template {document_id}. Triggering PDF processing and chunking first...")
                
                from backend.tasks.pdf_tasks import process_pdf_task
                from backend.tasks.chunking_tasks import chunk_document_task
                
                # Step A: Process PDF
                pdf_result = process_pdf_task(document_id, file_path, filename)
                if pdf_result.get("status") != "success":
                    return {
                        "status": "error",
                        "error": f"Failed to process template PDF: {pdf_result.get('error')}"
                    }
                    
                # Step B: Chunk the elements
                elements = pdf_result.get("elements", [])
                chunk_result = chunk_document_task(document_id, elements, filename)
                if chunk_result.get("status") != "success":
                    return {
                        "status": "error",
                        "error": f"Failed to chunk template elements: {chunk_result.get('error')}"
                    }
                
                logger.info(f"Successfully processed and chunked template contract {document_id} on the fly.")
            else:
                logger.info(f"No physical template file on disk for document {document_id}. Proceeding directly with prompt-only contract drafting.")

        # 3. Instantiate and run the deterministic LangGraph drafting orchestrator
        from backend.agents.contract_drafting_langgraph import ContractDraftingLangGraphRunner
        orchestrator = ContractDraftingLangGraphRunner()
        
        mode = "template" if chunks_count > 0 else "prompt_only"
        input_payload = {
            "document_id": document_id,
            "drafting_instructions": drafting_instructions,
            "contract_type": contract_type or (filename.split(".")[0] if filename else "Custom Contract"),
            "company_name": company_name,
            "counterparty_name": counterparty_name,
            "favor_party": favor_party or "Balanced",
            "governing_law": governing_law or "Indian Contract Act, 1872",
            "drafting_style": drafting_style or "Institutional Legal",
            "mode": mode,
        }
        
        agent_drafting_result = None
        
        # Establish logging directories and file
        log_dir = Path("backend/storage/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / f"{document_id}_drafting_execution.log"
        
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            def log_write(text: str):
                logger.info(text)
                print(text)
                log_file.write(text + "\n")
                log_file.flush()
                
            log_write("="*80)
            log_write(f">>> STARTING LANGGRAPH CONTRACT DRAFTING ({mode.upper()}) FOR DOCUMENT: {document_id}")
            log_write(f">>> Log file: {log_file_path}")
            log_write("="*80 + "\n")
            
            def run_stream_drafting():
                nonlocal agent_drafting_result
                for chunk in orchestrator.stream(
                    input_payload,
                    stream_mode="updates",
                    subgraphs=True,
                    version="v2",
                ):
                    if not isinstance(chunk, dict) or "type" not in chunk:
                        continue
                        
                    if chunk["type"] == "updates":
                        data = chunk.get("data", {})
                        for node_name, node_data in data.items():
                            log_write(f"\n[LangGraph Milestone Node: {node_name}]")
                            if isinstance(node_data, dict):
                                progress = node_data.get("progress_percentage", 50)
                                self.update_state(
                                    state="PROGRESS",
                                    meta={
                                        "milestone": node_name,
                                        "progress": progress,
                                        "document_id": document_id,
                                    }
                                )
                                if "structured_response" in node_data and node_data["structured_response"] is not None:
                                    agent_drafting_result = node_data["structured_response"]
                                    log_write("  └─ Extracted final structured drafting result.")
                                elif "current_draft_markdown" in node_data:
                                    log_write(f"  └─ Draft length: {len(node_data['current_draft_markdown'])} chars")

            execute_with_exponential_backoff(run_stream_drafting)
                                        
            log_write("\n" + "="*80)
            log_write(">>> LANGGRAPH CONTRACT DRAFTING COMPLETE")
            log_write("="*80 + "\n")
            
        if not agent_drafting_result:
            return {
                "status": "error",
                "document_id": document_id,
                "error": "Drafting orchestrator did not produce any result."
            }
            
        # 4. Save results to the outputs directory
        output_dir = Path("backend/storage/outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Serialize model output
        if hasattr(agent_drafting_result, "model_dump"):
            report_data = agent_drafting_result.model_dump()
        else:
            report_data = agent_drafting_result
            
        # Save drafted contract directly to the database
        contract_md = report_data.get("contract_markdown", "")
        try:
            from backend.services.contract_draft_service import save_or_update_draft_in_db
            save_or_update_draft_in_db(
                document_id=document_id,
                content=contract_md,
                contract_title=report_data.get("contract_title") or report_data.get("contract_type"),
                contract_type=report_data.get("contract_type"),
                parties=report_data.get("parties", []),
                blueprint=report_data.get("blueprint", []),
                legal_citations=report_data.get("legal_citations", []),
                review_comments=report_data.get("review_comments", []),
                compliance_score=report_data.get("compliance_score"),
            )
            logger.info(f"Contract draft saved to database for document {document_id}")
        except Exception as db_err:
            logger.error(f"Failed to save contract draft to DB in drafting task: {db_err}", exc_info=True)

        # Optional local file cache in outputs directory
        markdown_file = output_dir / f"{document_id}_drafted_contract.md"
        report_file = output_dir / f"{document_id}_drafting_report.json"
        try:
            with open(markdown_file, "w", encoding="utf-8") as f:
                f.write(contract_md)
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved drafted contract cache files to: {markdown_file}")
        except Exception as cache_err:
            logger.warning(f"Could not write draft cache files for {document_id}: {cache_err}")
        
        # Optional memory cache for backward compatibility
        try:
            memory_dir = Path("backend/storage/memories") / document_id
            memory_dir.mkdir(parents=True, exist_ok=True)
            memory_contract_file = memory_dir / "drafted_contract.md"
            with open(memory_contract_file, "w", encoding="utf-8") as f:
                f.write(contract_md)
        except Exception as copy_err:
            logger.warning(f"Failed to copy drafted contract to memory folder: {copy_err}")
            
        return {
            "status": "success",
            "document_id": document_id,
            "drafted_contract_file": str(markdown_file),
            "drafting_report_file": str(report_file),
            "result": report_data
        }
        
    except Exception as e:
        error_msg = f"Drafting task failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg
        }


@celery_app.task(bind=True, name="run_agent_reiteration_task")
def run_agent_reiteration_task(
    self,
    document_id: str,
    instructions: str,
) -> dict[str, Any]:
    """
    Background task to run the Contract Drafting Orchestrator agent in reiteration/edit mode.
    Loads persistent filesystem memory and previous draft, preventing re-analysis of the PDF structure and initial research.
    """
    try:
        logger.info(f"Starting contract reiteration for document: {document_id}")
        
        # 1. Verify document exists in DB
        with SessionLocal() as db:
            result = db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                error_msg = f"Document template with ID {document_id} not found in database"
                logger.error(error_msg)
                return {"status": "error", "error": error_msg}
                
        # 2. Instantiate and run the deterministic LangGraph drafting orchestrator in reiteration mode
        from backend.agents.contract_drafting_langgraph import ContractDraftingLangGraphRunner
        orchestrator = ContractDraftingLangGraphRunner()
        
        input_payload = {
            "document_id": document_id,
            "drafting_instructions": instructions,
            "mode": "reiteration",
        }
        
        agent_drafting_result = None
        
        # Establish logging directories and file
        log_dir = Path("backend/storage/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / f"{document_id}_reiteration_execution.log"
        
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            def log_write(text: str):
                logger.info(text)
                print(text)
                log_file.write(text + "\n")
                log_file.flush()
                
            log_write("="*80)
            log_write(f">>> STARTING LANGGRAPH CONTRACT REITERATION FOR DOCUMENT: {document_id}")
            log_write(f">>> Log file: {log_file_path}")
            log_write("="*80 + "\n")
            
            def run_stream_reiterate():
                nonlocal agent_drafting_result
                for chunk in orchestrator.stream(
                    input_payload,
                    stream_mode="updates",
                    subgraphs=True,
                    version="v2",
                ):
                    if not isinstance(chunk, dict) or "type" not in chunk:
                        continue
                        
                    if chunk["type"] == "updates":
                        data = chunk.get("data", {})
                        for node_name, node_data in data.items():
                            log_write(f"\n[LangGraph Milestone Node: {node_name}]")
                            if isinstance(node_data, dict):
                                progress = node_data.get("progress_percentage", 60)
                                self.update_state(
                                    state="PROGRESS",
                                    meta={
                                        "milestone": node_name,
                                        "progress": progress,
                                        "document_id": document_id,
                                    }
                                )
                                if "structured_response" in node_data and node_data["structured_response"] is not None:
                                    agent_drafting_result = node_data["structured_response"]
                                    log_write("  └─ Extracted updated structured reiteration result.")
                                elif "current_draft_markdown" in node_data:
                                    log_write(f"  └─ Updated draft length: {len(node_data['current_draft_markdown'])} chars")

            execute_with_exponential_backoff(run_stream_reiterate)
                                        
            log_write("\n" + "="*80)
            log_write(">>> LANGGRAPH CONTRACT REITERATION COMPLETE")
            log_write("="*80 + "\n")
            
        if not agent_drafting_result:
            return {
                "status": "error",
                "document_id": document_id,
                "error": "Drafting orchestrator did not produce any result for reiteration."
            }
            
        # 3. Save results to the outputs directory
        output_dir = Path("backend/storage/outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Serialize model output
        if hasattr(agent_drafting_result, "model_dump"):
            report_data = agent_drafting_result.model_dump()
        else:
            report_data = agent_drafting_result
            
        # Save updated contract directly to the database
        contract_md = report_data.get("contract_markdown", "")
        try:
            from backend.services.contract_draft_service import save_or_update_draft_in_db
            save_or_update_draft_in_db(
                document_id=document_id,
                content=contract_md,
                contract_title=report_data.get("contract_title") or report_data.get("contract_type"),
                contract_type=report_data.get("contract_type"),
                parties=report_data.get("parties", []),
                blueprint=report_data.get("blueprint", []),
                legal_citations=report_data.get("legal_citations", []),
                review_comments=report_data.get("review_comments", []),
                compliance_score=report_data.get("compliance_score"),
            )
            logger.info(f"Reiterated contract draft saved to database for document {document_id}")
        except Exception as db_err:
            logger.error(f"Failed to save reiterated contract draft to DB: {db_err}", exc_info=True)

        # Optional local file cache in outputs directory
        markdown_file = output_dir / f"{document_id}_drafted_contract.md"
        report_file = output_dir / f"{document_id}_drafting_report.json"
        try:
            with open(markdown_file, "w", encoding="utf-8") as f:
                f.write(contract_md)
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved updated drafted contract cache to: {markdown_file}")
        except Exception as cache_err:
            logger.warning(f"Could not write reiteration cache files for {document_id}: {cache_err}")
        
        # Optional memory cache for backward compatibility
        try:
            memory_dir = Path("backend/storage/memories") / document_id
            memory_dir.mkdir(parents=True, exist_ok=True)
            memory_contract_file = memory_dir / "drafted_contract.md"
            with open(memory_contract_file, "w", encoding="utf-8") as f:
                f.write(contract_md)
        except Exception as copy_err:
            logger.warning(f"Failed to copy updated contract to memory folder: {copy_err}")
            
        return {
            "status": "success",
            "document_id": document_id,
            "drafted_contract_file": str(markdown_file),
            "drafting_report_file": str(report_file),
            "result": report_data
        }
        
    except Exception as e:
        error_msg = f"Reiteration task failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": "error",
            "document_id": document_id,
            "error": error_msg
        }
