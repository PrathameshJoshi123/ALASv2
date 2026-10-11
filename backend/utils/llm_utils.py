"""
LLM Utilities module providing resilient model initialization and exponential
backoff retry helpers for Mistral API calls.
"""

import os
import logging
from typing import Any, Callable, TypeVar
from dotenv import load_dotenv

load_dotenv()
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception,
)
from langchain_mistralai import ChatMistralAI
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar("T")

# Main orchestrator model: ministral-14b-2512
ORCHESTRATOR_MODEL_NAME = "ministral-14b-2512"
# Specialist agent model: ministral-3b-2512
SPECIALIST_MODEL_NAME = "ministral-3b-2512"


def is_rate_limit_or_transient_error(exc: Exception) -> bool:
    """
    Check if an exception is a 429 Rate Limit or transient network error.
    """
    if exc is None:
        return False
    
    err_str = str(exc).lower()
    is_rate_limit = (
        "429" in err_str
        or "rate limit" in err_str
        or "rate_limited" in err_str
        or "too many requests" in err_str
        or "1300" in err_str
    )
    is_transient = (
        "timeout" in err_str
        or "connection error" in err_str
        or "service unavailable" in err_str
        or "503" in err_str
        or "502" in err_str
    )
    
    if is_rate_limit or is_transient:
        logger.warning(f"Detected rate limit / transient API error: {exc}. Will retry with exponential backoff.")
        return True
        
    return False


def get_resilient_llm(
    model_name: str,
    temperature: float = 0.0,
    max_retries: int | None = None,
    timeout: int | None = None,
) -> ChatMistralAI:
    """
    Factory to instantiate a ChatMistralAI model compatible with deepagents.
    
    Args:
        model_name: Name of the Mistral model (e.g. 'ministral-14b-2512', 'ministral-3b-2512')
        temperature: Sampling temperature
        max_retries: Max retries parameter for ChatMistralAI internal handler
        timeout: Request timeout in seconds
    """
    api_key = os.environ.get("MISTRAL_API_KEY") or os.environ.get("MISTRALAI_API_KEY") or settings.MISTRAL_API_KEY
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY environment variable is not configured.")

    retries = max_retries if max_retries is not None else settings.MISTRAL_MAX_RETRIES
    t_out = timeout if timeout is not None else settings.MISTRAL_API_TIMEOUT

    return ChatMistralAI(
        model=model_name,
        api_key=api_key,
        temperature=temperature,
        timeout=t_out,
        max_retries=retries,
    )


def execute_with_exponential_backoff(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 6,
    initial_wait: float = 2.0,
    max_wait: float = 60.0,
    **kwargs: Any,
) -> T:
    """
    Execute a function with exponential backoff retries when rate limit or transient errors occur.
    
    Args:
        func: Callable function to execute
        max_attempts: Maximum number of attempts
        initial_wait: Initial backoff delay in seconds
        max_wait: Maximum wait ceiling in seconds
    """
    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=initial_wait, max=max_wait),
        retry=retry_if_exception(is_rate_limit_or_transient_error),
        reraise=True,
    )
    def _retry_wrapper():
        return func(*args, **kwargs)

    return _retry_wrapper()
