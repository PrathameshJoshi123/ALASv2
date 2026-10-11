import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain_core.messages import HumanMessage
from langchain_mistralai import ChatMistralAI

from backend.config import settings

logger = logging.getLogger(__name__)

# Default model for vision tasks in Mistral is Pixtral
DEFAULT_VISION_MODEL = "pixtral-12b-2409"

def encode_image_to_base64(image_path: Path | str) -> str:
    """Encode image to base64 string."""
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found at: {image_path}")
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def get_vision_client() -> Any:
    """Initialize ChatMistralAI for vision completions with exponential backoff retries."""
    from backend.utils.llm_utils import get_resilient_llm
    return get_resilient_llm(model_name=DEFAULT_VISION_MODEL, temperature=0.0)

def analyze_case_image(image_path: Path | str) -> Dict[str, Any]:
    """
    Submit an image to Mistral Pixtral to perform OCR, visual description,
    and metadata extraction.
    
    Args:
        image_path: Path to the image file.
        
    Returns:
        Dictionary containing extracted metadata:
        {
            "extracted_text": str (OCR text if any),
            "visual_description": str (detailed visual summary),
            "key_objects": list[str],
            "timeline_timestamp": str (ISO date format, or null),
            "detected_timeline_event": str (short summary for timeline)
        }
    """
    image_path = Path(image_path)
    logger.info(f"Submitting image {image_path.name} to Mistral vision model...")
    
    try:
        base64_data = encode_image_to_base64(image_path)
        mime_type = "image/jpeg"
        if image_path.suffix.lower() == ".png":
            mime_type = "image/png"
        elif image_path.suffix.lower() == ".gif":
            mime_type = "image/gif"
        elif image_path.suffix.lower() == ".webp":
            mime_type = "image/webp"
            
        client = get_vision_client()
        
        prompt = """
        You are a high-precision legal visual analysis assistant.
        Analyze the provided image and extract key details for a legal case file.
        
        You must return a raw JSON object with the following fields:
        {
            "extracted_text": "any written text, OCR transcription, document headers, signatures, stamps, license plates, numbers or handwriting visible in the image",
            "visual_description": "a thorough description of the visual scene, details of physical damage, weapons, locations, injuries, objects, or documents shown",
            "key_objects": ["list of important objects identified in the image, e.g., 'damaged bumper', 'signature block', 'official stamp', 'weapon'"],
            "timeline_timestamp": "ISO 8601 formatted date/time string (YYYY-MM-DDTHH:MM:SS) representing any event timestamp or document creation date visible in the image, or null if none",
            "detected_timeline_event": "a brief 1-sentence summary of the event represented by this image for a chronology timeline, or null if none"
        }
        
        Ensure your output contains ONLY the raw JSON object. Do not wrap in markdown or add explanations.
        """
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64_data}"},
                },
            ]
        )
        
        response = client.invoke([message])
        content = response.content.strip()
        
        # Clean markdown code block wraps if present
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        parsed_result = json.loads(content)
        
        # Format validate fields
        result = {
            "extracted_text": parsed_result.get("extracted_text") or "",
            "visual_description": parsed_result.get("visual_description") or "",
            "key_objects": parsed_result.get("key_objects") or [],
            "timeline_timestamp": parsed_result.get("timeline_timestamp"),
            "detected_timeline_event": parsed_result.get("detected_timeline_event"),
        }
        
        logger.info(f"Successfully processed image {image_path.name}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to analyze image {image_path}: {e}", exc_info=True)
        # Return fallback dictionary to prevent pipeline crashes
        return {
            "extracted_text": "",
            "visual_description": f"Failed to analyze image due to error: {str(e)}",
            "key_objects": [],
            "timeline_timestamp": None,
            "detected_timeline_event": None
        }
