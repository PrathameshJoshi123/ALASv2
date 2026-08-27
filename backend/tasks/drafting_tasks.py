import json
import logging
from pathlib import Path
from typing import Any

from celery import chain
from backend.celery_app import celery_app
from celery.utils.log import get_task_logger

from langchain_core.messages import HumanMessage
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
            
        # 2. Trigger auto-processing if chunks are 0
        if chunks_count == 0:
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

        # 3. Instantiate and run the drafting orchestrator
        from backend.agents.contract_drafting_orchestrator import create_contract_drafting_orchestrator
        orchestrator = create_contract_drafting_orchestrator(document_id)
        
        agent_msg = (
            f"Draft a new contract using template document ID: {document_id}. "
            f"Here are the drafting instructions:\n{drafting_instructions}"
        )
        
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
            log_write(f">>> STARTING DEEP AGENT CONTRACT DRAFTING FOR DOCUMENT TEMPLATE: {document_id}")
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
                    
                    if ns:
                        path_str = " -> ".join(ns)
                        log_write(f"\n[Subagent: {path_str}] running node...")
                        for node_name, node_data in data.items():
                            log_write(f"  └─ Step: {node_name}")
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
                        log_write("\n[Main Drafting Coordinator Agent] running node...")
                        for node_name, node_data in data.items():
                            log_write(f"  └─ Step: {node_name}")
                            
                            # Extract structured response from coordinator
                            if isinstance(node_data, dict):
                                if "structured_response" in node_data and node_data["structured_response"] is not None:
                                    agent_drafting_result = node_data["structured_response"]
                                elif "response" in node_data and node_data["response"] is not None:
                                    agent_drafting_result = node_data["response"]
                                    
                            if node_name == "tools" and isinstance(node_data, dict) and "messages" in node_data:
                                for msg in node_data["messages"]:
                                    if msg.type == "tool" and msg.name == "task":
                                        log_write(f"\n>>> Subagent execution completed: {msg.name}")
                                        log_write(f"    Result snippet: {str(msg.content)[:300]}...")
                                        
            log_write("\n" + "="*80)
            log_write(">>> DEEP AGENT CONTRACT DRAFTING COMPLETE")
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
            
        # Save drafted contract markdown file
        contract_md = report_data.get("contract_markdown", "")
        markdown_file = output_dir / f"{document_id}_drafted_contract.md"
        with open(markdown_file, "w", encoding="utf-8") as f:
            f.write(contract_md)
        logger.info(f"Saved drafted contract Markdown to: {markdown_file}")
        
        # Save metadata report JSON
        report_file = output_dir / f"{document_id}_drafting_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved drafting metadata report to: {report_file}")
        
        # Also copy/save the contract to the memory folder so the agent loads it in next reiterations
        try:
            memory_dir = Path("backend/storage/memories") / document_id
            memory_dir.mkdir(parents=True, exist_ok=True)
            memory_contract_file = memory_dir / "drafted_contract.md"
            with open(memory_contract_file, "w", encoding="utf-8") as f:
                f.write(contract_md)
            logger.info(f"Copied drafted contract to memory folder: {memory_contract_file}")
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
                
        # 2. Instantiate and run the drafting orchestrator
        from backend.agents.contract_drafting_orchestrator import create_contract_drafting_orchestrator
        orchestrator = create_contract_drafting_orchestrator(document_id)
        
        # Format the user message for reiteration mode
        agent_msg = (
            f"The user wants to reiterate and apply specific edits to the previously drafted contract. "
            f"Please read the old memory from `/memories/drafting_memory.md` and the existing draft from `/memories/drafted_contract.md`. "
            f"AVOID re-running structural template parsing or initial legal research since they are already analyzed. "
            f"Here are the instructions/comments for the requested edits:\n{instructions}\n\n"
            f"Perform the edits and update both the contract draft and memory files as needed."
        )
        
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
            log_write(f">>> STARTING DEEP AGENT CONTRACT REITERATION FOR DOCUMENT: {document_id}")
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
                    
                    if ns:
                        path_str = " -> ".join(ns)
                        log_write(f"\n[Subagent: {path_str}] running node...")
                        for node_name, node_data in data.items():
                            log_write(f"  └─ Step: {node_name}")
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
                        log_write("\n[Main Drafting Coordinator Agent] running node...")
                        for node_name, node_data in data.items():
                            log_write(f"  └─ Step: {node_name}")
                            
                            # Extract structured response from coordinator
                            if isinstance(node_data, dict):
                                if "structured_response" in node_data and node_data["structured_response"] is not None:
                                    agent_drafting_result = node_data["structured_response"]
                                elif "response" in node_data and node_data["response"] is not None:
                                    agent_drafting_result = node_data["response"]
                                    
                            if node_name == "tools" and isinstance(node_data, dict) and "messages" in node_data:
                                for msg in node_data["messages"]:
                                    if msg.type == "tool" and msg.name == "task":
                                        log_write(f"\n>>> Subagent execution completed: {msg.name}")
                                        log_write(f"    Result snippet: {str(msg.content)[:300]}...")
                                        
            log_write("\n" + "="*80)
            log_write(">>> DEEP AGENT CONTRACT REITERATION COMPLETE")
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
            
        # Save updated contract markdown file
        contract_md = report_data.get("contract_markdown", "")
        markdown_file = output_dir / f"{document_id}_drafted_contract.md"
        with open(markdown_file, "w", encoding="utf-8") as f:
            f.write(contract_md)
        logger.info(f"Saved updated drafted contract Markdown to: {markdown_file}")
        
        # Save updated metadata report JSON
        report_file = output_dir / f"{document_id}_drafting_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved updated drafting metadata report to: {report_file}")
        
        # Also copy the updated contract to the memory folder so they stay in sync
        try:
            memory_dir = Path("backend/storage/memories") / document_id
            memory_dir.mkdir(parents=True, exist_ok=True)
            memory_contract_file = memory_dir / "drafted_contract.md"
            with open(memory_contract_file, "w", encoding="utf-8") as f:
                f.write(contract_md)
            logger.info(f"Copied updated contract to memory folder: {memory_contract_file}")
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
