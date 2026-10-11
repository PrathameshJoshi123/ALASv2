import json
import logging
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from celery.utils.log import get_task_logger
from langchain_core.messages import HumanMessage
from backend.utils.llm_utils import execute_with_exponential_backoff

from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.models.cases import Case, CaseDocument, CaseDocumentChunk, EvidenceDetail, CaseAnalysis
from backend.services.pdf_service import pdf_service
from backend.services.image_extractor import process_file_images
from backend.services.vision_service import analyze_case_image
from backend.services.case_vector_storage import store_case_chunks_in_vector_db
from backend.services.chunking.pipeline import ChunkingPipeline

logger = get_task_logger(__name__)

def execute_process_case_document(document_id: str) -> dict[str, Any]:
    """
    Core function to process a case document:
    1. Scan and extract all embedded/standalone images.
    2. Analyze images via Mistral Pixtral (OCR + visual summary) and cache results.
    3. If PDF, extract elements and chunk them.
    4. Save text chunks to the database and index them in case ChromaDB.
    """
    logger.info(f"Starting case document processing for document: {document_id}")
    
    with SessionLocal() as db:
        document = db.execute(
            select_document_by_id(document_id)
        ).scalar_one_or_none()
        
        if not document:
            error_msg = f"Document {document_id} not found in database."
            logger.error(error_msg)
            return {"status": "error", "error": error_msg}
            
        file_path = Path(document.storage_link)
        if not file_path.exists():
            error_msg = f"File not found on disk at: {document.storage_link}"
            document.status = "error"
            db.commit()
            return {"status": "error", "error": error_msg}
            
        case_id = document.case_id
        document.status = "processing"
        db.commit()
        
        try:
            # 1. Image extraction & processing (multimodal cache)
            extracted_images = process_file_images(file_path, document_id)
            for img_info in extracted_images:
                img_path = img_info["image_path"]
                page_num = img_info["page_number"]
                
                # Call Mistral Pixtral for OCR + descriptions
                analysis = analyze_case_image(img_path)
                
                # Check for timeline timestamp
                timeline_dt = None
                if analysis.get("timeline_timestamp"):
                    try:
                        timeline_dt = datetime.fromisoformat(analysis["timeline_timestamp"])
                    except ValueError:
                        pass
                        
                # Create EvidenceDetail cache record
                evidence = EvidenceDetail(
                    case_document_id=document_id,
                    page_number=page_num,
                    image_path=img_path,
                    extracted_text=analysis.get("extracted_text"),
                    visual_description=analysis.get("visual_description", ""),
                    key_objects=analysis.get("key_objects", []),
                    timeline_timestamp=timeline_dt,
                    detected_timeline_event=analysis.get("detected_timeline_event")
                )
                db.add(evidence)
            db.commit()
            
            # 2. Text elements parsing and chunking (if PDF)
            if file_path.suffix.lower() == ".pdf":
                elements = pdf_service.process_pdf(file_path=file_path, filename=document.name)
                
                # Run elements through chunking pipeline
                pipeline = ChunkingPipeline()
                documents = pipeline.process(elements, document_id, document.name)
                
                saved_chunks = []
                for idx, doc in enumerate(documents, start=1):
                    chunk = CaseDocumentChunk(
                        document_id=document_id,
                        content=doc.page_content,
                        chunk_metadata=doc.metadata,
                        page_start=doc.metadata.get("page_start"),
                        page_end=doc.metadata.get("page_end"),
                        sequence_number=idx
                    )
                    db.add(chunk)
                    saved_chunks.append(chunk)
                db.commit()
                
                # Index chunks in case Chroma DB
                store_case_chunks_in_vector_db(saved_chunks, case_id, document_id)
                
            document.status = "completed"
            db.commit()
            
            return {
                "status": "success",
                "document_id": document_id,
                "images_extracted": len(extracted_images)
            }
            
        except Exception as e:
            logger.error(f"Failed to process case document {document_id}: {e}", exc_info=True)
            document.status = "error"
            db.commit()
            return {"status": "error", "error": str(e)}

@celery_app.task(bind=True, name="process_case_document_task")
def process_case_document_task(self, document_id: str) -> dict[str, Any]:
    """Background Celery wrapper for document processing."""
    return execute_process_case_document(document_id)

@celery_app.task(bind=True, name="analyze_case_task")
def analyze_case_task(self, case_id: str) -> dict[str, Any]:
    """
    Asynchronously runs the complete case analysis pipeline:
    1. Ensures all attached case documents are processed, chunked, and indexed in ChromaDB vector DB.
    2. Runs the CaseOrchestrator multi-agent loop to perform complete legal analysis.
    3. Stores the compiled CaseAnalysisResult inside CaseAnalysis in the database.
    """
    logger.info(f"Starting case analysis pipeline task for case: {case_id}")
    
    with SessionLocal() as db:
        case = db.execute(
            select_case_by_id(case_id)
        ).scalar_one_or_none()
        
        if not case:
            error_msg = f"Case {case_id} not found."
            logger.error(error_msg)
            return {"status": "error", "error": error_msg}
            
        case.status = "processing"
        db.commit()

        # Step 1: Guarantee that all case documents are processed and chunked first
        docs = case.documents or []
        unprocessed_docs = [d for d in docs if d.status != "completed"]
        logger.info(f"Case {case_id}: Found {len(unprocessed_docs)} document(s) needing parsing & chunking before agent analysis.")

        for doc in unprocessed_docs:
            logger.info(f"Running parsing & chunking pipeline for document {doc.id} ({doc.name})...")
            res = execute_process_case_document(doc.id)
            logger.info(f"Completed document processing for {doc.id}: status={res.get('status')}")

        # Step 2: Establish logging directories and stream agent execution to file
        log_dir = Path("backend/storage/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / f"{case_id}_case_agent_execution.log"

        try:
            from backend.agents.case_orchestrator import create_case_orchestrator
            orchestrator = create_case_orchestrator()
            agent_msg = f"Analyze legal case with ID: {case_id}"

            result_data = None

            with open(log_file_path, "w", encoding="utf-8") as log_file:
                def log_write(text: str):
                    logger.info(text)
                    print(text, flush=True)
                    log_file.write(text + "\n")
                    log_file.flush()

                log_write("=" * 80)
                log_write(f">>> STARTING DEEP AGENT CASE FILE ANALYSIS FOR CASE: {case_id}")
                log_write(f">>> Log file: {log_file_path}")
                log_write("=" * 80 + "\n")

                def run_stream_case_analysis():
                    nonlocal result_data
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

                # Run streaming execution with backoff
                execute_with_exponential_backoff(run_stream_case_analysis)

                # Invoke direct fallback if stream didn't capture final dict
                if not result_data:
                    response = execute_with_exponential_backoff(
                        orchestrator.invoke,
                        {"messages": [HumanMessage(content=agent_msg)]}
                    )
                    if hasattr(response, "model_dump"):
                        result_data = response.model_dump()
                    elif isinstance(response, dict):
                        result_data = response
                    else:
                        result_data = getattr(response, "content", str(response))

            if isinstance(result_data, str):
                try:
                    result_data = json.loads(result_data)
                except ValueError:
                    result_data = {"raw_report": result_data}

            # Save report to storage output file
            output_dir = Path("backend/storage/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{case_id}_analysis_report.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=2, default=str)

            # Save findings report inside CaseAnalysis table in DB
            analysis = db.execute(
                select_analysis_by_case_and_type(case_id, "full_case_analysis")
            ).scalar_one_or_none()

            if analysis:
                analysis.content = result_data
            else:
                analysis = CaseAnalysis(
                    case_id=case_id,
                    analysis_type="full_case_analysis",
                    content=result_data
                )
                db.add(analysis)

            # Extract timeline items from result_data if present
            if isinstance(result_data, dict) and "timeline" in result_data and isinstance(result_data["timeline"], list):
                from backend.models.cases import CaseTimeline
                for item in result_data["timeline"]:
                    if isinstance(item, dict) and item.get("event_description"):
                        try:
                            date_str = item.get("event_date", datetime.now().isoformat())
                            try:
                                event_dt = datetime.fromisoformat(date_str)
                            except ValueError:
                                event_dt = datetime.now()

                            timeline_entry = CaseTimeline(
                                case_id=case_id,
                                event_date=event_dt,
                                event_description=item["event_description"],
                                source_document_id=item.get("source_document_id"),
                                source_page=item.get("source_page"),
                                citation_quote=item.get("citation_quote")
                            )
                            db.add(timeline_entry)
                        except Exception as t_err:
                            logger.warning(f"Skipped timeline entry import: {t_err}")

            case.status = "analyzed"
            db.commit()

            return {
                "status": "success",
                "case_id": case_id,
                "result": result_data
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze case {case_id}: {e}", exc_info=True)
            case.status = "error"
            db.commit()
            return {"status": "error", "error": str(e)}

# Helper queries to isolate DB code
def select_document_by_id(doc_id: str):
    from sqlalchemy import select
    return select(CaseDocument).where(CaseDocument.id == doc_id)

def select_case_by_id(case_id: str):
    from sqlalchemy import select
    return select(Case).where(Case.id == case_id)

def select_analysis_by_case_and_type(case_id: str, type_str: str):
    from sqlalchemy import select
    return select(CaseAnalysis).where(Case.id == case_id).where(CaseAnalysis.analysis_type == type_str)
