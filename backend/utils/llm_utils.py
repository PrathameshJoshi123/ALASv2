"""
LLM Utilities module providing resilient model initialization and exponential
backoff retry helpers for Mistral API calls.
"""

import os
import re
import json
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

# Main orchestrator high-reasoning model: mistral-small-2603
ORCHESTRATOR_MODEL_NAME = os.environ.get("MISTRAL_ORCHESTRATOR_MODEL", "ministral-14b-latest")
# Specialist agent model: ministral-8b-latest
SPECIALIST_MODEL_NAME = os.environ.get("MISTRAL_MODEL", "ministral-8b-latest")


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


def clean_json_response(content: str) -> str:
    """Strip markdown json code fences from LLM responses."""
    cleaned = content.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()
    return cleaned


def safe_parse_json(content: str) -> Any:
    """
    Robustly parse JSON responses from LLMs.
    Uses LangChain's JsonOutputParser with resilient multi-pass repairs for:
    - unquoted keys ('Expecting property name enclosed in double quotes')
    - single-quoted keys and properties
    - JavaScript/C-style comments
    - unescaped Windows paths and invalid backslash escapes
    - unescaped control characters (raw newlines/tabs in string literals)
    - trailing commas before closing braces/brackets
    - unclosed/truncated brackets
    """
    cleaned = clean_json_response(content)

    # Attempt 1: Direct LangChain JsonOutputParser
    try:
        from langchain_core.output_parsers import JsonOutputParser
        return JsonOutputParser().parse(cleaned)
    except Exception:
        pass

    def _strip_comments(s: str) -> str:
        s = re.sub(r'//[^\n\r]*', '', s)
        s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
        return s

    def _quote_unquoted_keys(s: str) -> str:
        # Turn unquoted keys like overall_risk_score: 38.5 into "overall_risk_score": 38.5
        return re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', s)

    def _fix_single_quotes(s: str) -> str:
        # Turn single-quoted keys like 'overall_risk_score': into "overall_risk_score":
        s = re.sub(r"([{,]\s*)'([a-zA-Z0-9_]+)'\s*:", r'\1"\2":', s)
        # Turn single-quoted values like: 'value' into: "value"
        s = re.sub(r":\s*'([^']*)'", r': "\1"', s)
        return s

    def _clean_invalid_escapes(s: str) -> str:
        # Escape any backslash not part of a valid JSON escape: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        return re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', s)

    def _strip_controls(s: str) -> str:
        chars = []
        for ch in s:
            code = ord(ch)
            if code < 32:
                if ch in '\n\r\t':
                    chars.append(' ')
            elif 127 <= code <= 159:
                pass
            else:
                chars.append(ch)
        return "".join(chars)

    def _clean_trailing_commas(s: str) -> str:
        return re.sub(r',\s*([\]\}])', r'\1', s)

    def _strip_markdown_bold(s: str) -> str:
        # Remove LLM hallucinated markdown bold markers inside JSON tokens
        return s.replace("**", "")

    def _clean_trailing_annotations(s: str) -> str:
        lines = s.splitlines()
        repaired = []
        for line in lines:
            # Strip trailing annotations like (Clause 12). outside quotes
            line = re.sub(r'(:\s*"[^"]*")\s*\([^)]*\)\.?', r'\1', line)
            repaired.append(line)
        return "\n".join(repaired)

    def _fix_inner_quotes(s: str) -> str:
        lines = s.splitlines()
        repaired = []
        for line in lines:
            m = re.match(r'^(\s*"[a-zA-Z0-9_]+"\s*:\s*")(.*)(",?\s*)$', line)
            if m:
                prefix, inner, suffix = m.group(1), m.group(2), m.group(3)
                escaped_inner = re.sub(r'(?<!\\)"', r'\"', inner)
                repaired.append(prefix + escaped_inner + suffix)
            else:
                repaired.append(line)
        return "\n".join(repaired)

    # Step 1: Apply structural text repairs while newlines are preserved
    s1 = _strip_comments(cleaned)
    s1 = _strip_markdown_bold(s1)
    s1 = _clean_trailing_annotations(s1)
    s1 = _fix_single_quotes(s1)
    s1 = _quote_unquoted_keys(s1)
    s1 = _fix_inner_quotes(s1)
    s1 = _clean_trailing_commas(s1)
    s1 = _clean_invalid_escapes(s1)

    # Attempt 2: LangChain parser on structurally repaired string
    try:
        from langchain_core.output_parsers import JsonOutputParser
        return JsonOutputParser().parse(s1)
    except Exception:
        pass

    # Attempt 3: Standard json.loads on repaired string
    try:
        return json.loads(s1, strict=False)
    except Exception:
        pass

    # Step 2: Strip unescaped control chars and fix inner quotes
    s2 = _strip_controls(s1)
    s2 = _fix_inner_quotes(s2)

    # Attempt 4: json.loads on control-stripped string
    try:
        return json.loads(s2, strict=False)
    except Exception:
        pass

    # Attempt 5: Outermost JSON object / array
    try:
        m = re.search(r'(\{.*\}|\[.*\])', s2, re.DOTALL)
        if m:
            return json.loads(m.group(0), strict=False)
    except Exception:
        pass

    # Attempt 6: Truncated JSON repair (balance brackets)
    try:
        open_braces = s2.count('{') - s2.count('}')
        open_brackets = s2.count('[') - s2.count(']')
        repaired = s2.rstrip()
        if repaired.endswith(','):
            repaired = repaired[:-1]
        repaired += (']' * max(0, open_brackets)) + ('}' * max(0, open_braces))
        return json.loads(repaired, strict=False)
    except Exception:
        pass

    # Final attempt with LangChain parser fallback
    from langchain_core.output_parsers import JsonOutputParser
    return JsonOutputParser().parse(s2)
