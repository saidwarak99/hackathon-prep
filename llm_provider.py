import os
import re
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
from google import genai
from google.genai import types
from db import sanitize_error

# Ensure project root .env is loaded reliably regardless of working directory
_ENV_PATH = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv
    if _ENV_PATH.exists():
        load_dotenv(dotenv_path=_ENV_PATH, override=True)
    else:
        load_dotenv(override=True)
except ImportError:
    pass

logger = logging.getLogger("restaurant_llm_provider")

DEFAULT_GENERATION_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


def get_gemini_api_key() -> Optional[str]:
    """Retrieves the Gemini API key, ensuring environment is properly loaded."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key and _ENV_PATH.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=_ENV_PATH, override=True)
            key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        except ImportError:
            pass
    return key.strip() if key else None


class LLMProviderError(Exception):
    """Base exception for all LLM provider errors."""
    pass


class QuotaExhaustedError(LLMProviderError):
    """
    Raised when daily or free-tier quota is exhausted.
    This condition is non-transient until reset; it must NOT be retried repeatedly.
    """
    def __init__(self, message: str, raw_error: Optional[str] = None):
        super().__init__(message)
        self.raw_error = raw_error


class RateLimitError(LLMProviderError):
    """
    Raised when short-term request rate limit (e.g. RPM / TPM) is exceeded.
    May be retried only if retry delay advice is short.
    """
    def __init__(self, message: str, retry_after: Optional[float] = None, raw_error: Optional[str] = None):
        super().__init__(message)
        self.retry_after = retry_after
        self.raw_error = raw_error


class ProviderOverloadError(LLMProviderError):
    """
    Raised when provider service is temporarily unavailable or overloaded (e.g. 503 UNAVAILABLE).
    """
    def __init__(self, message: str, raw_error: Optional[str] = None):
        super().__init__(message)
        self.raw_error = raw_error


class ModelNotFoundError(LLMProviderError):
    """Raised when requested model is not found, deprecated, or unavailable."""
    def __init__(self, message: str, raw_error: Optional[str] = None):
        super().__init__(message)
        self.raw_error = raw_error


class ProviderAuthError(LLMProviderError):
    """Raised when authentication / API key is missing or invalid."""
    pass


def classify_llm_error(e: Exception) -> LLMProviderError:
    """
    Classifies raw provider exceptions into specific domain error categories:
    - QuotaExhaustedError: Daily / billing quota exhausted (non-retryable).
    - RateLimitError: Transient rate limit (per minute / short burst).
    - ProviderOverloadError: 503 / UNAVAILABLE / high demand.
    - ModelNotFoundError: 404 / deprecated or missing model name.
    - ProviderAuthError: Missing or invalid API key.
    - LLMProviderError: Generic provider errors.
    Ensures all error messages are thoroughly sanitized of sensitive tokens and credentials.
    Ensures quota exhaustion is never misclassified as an auth or configuration error.
    """
    safe_str = sanitize_error(e)
    safe_lower = safe_str.lower()
    code = getattr(e, "code", None)

    # Check for retry guidance in error message
    retry_match = re.search(r"(?:retry\s*(?:in|after)|retry-after[:\s]+)\s*(\d+(?:\.\d+)?)\s*s\b", safe_str, re.IGNORECASE)
    retry_after = float(retry_match.group(1)) if retry_match else None

    # 1. Transient Rate Limit (RPM / short burst with provider retry guidance <= 60s)
    if retry_after is not None and retry_after <= 60.0:
        msg = "Gemini request rate limit exceeded."
        msg += f" Retry guidance: wait {retry_after:.1f}s."
        return RateLimitError(msg, retry_after=retry_after, raw_error=safe_str)

    # 2. Daily / Account Quota Exhaustion
    # (Prevents provider errors mentioning quota or billing from ever becoming ProviderAuthError)
    is_daily_quota = bool(re.search(
        r"quota exceeded|generaterequestsperday|requests_per_day|per day|free tier|check.*quota|plan and billing|resource_exhausted|exceeded your current quota",
        safe_lower
    ))

    if is_daily_quota or (retry_after is not None and retry_after > 60.0):
        return QuotaExhaustedError(
            "Gemini request quota has been exhausted. Please wait for daily quota reset or configure a paid API tier.",
            raw_error=safe_str
        )

    # Fallback 429 without short retry
    if code == 429 and (retry_after is None or retry_after > 5.0):
        if any(k in safe_lower for k in ["quota", "resource_exhausted", "limit"]):
            return QuotaExhaustedError(
                "Gemini request quota or resource limit exceeded.",
                raw_error=safe_str
            )

    # Fallback transient Rate Limit
    if "rate limit" in safe_lower:
        return RateLimitError("Gemini request rate limit exceeded.", retry_after=retry_after, raw_error=safe_str)

    # 3. Check for Provider Overload (503 UNAVAILABLE / overloaded)
    if code == 503 or any(k in safe_lower for k in ["503", "unavailable", "overloaded", "high demand"]):
        return ProviderOverloadError(
            "Gemini provider is temporarily overloaded (503 UNAVAILABLE).",
            raw_error=safe_str
        )

    # 4. Check for Model Not Found / Deprecated
    if code == 404 or any(k in safe_lower for k in ["not_found", "model not found", "no longer available"]):
        return ModelNotFoundError(
            f"The specified Gemini model is unavailable or deprecated: {safe_str}",
            raw_error=safe_str
        )

    # 5. Check for genuine authentication / authorization issues (ONLY if not quota/billing)
    auth_indicators = [
        "api_key not found", "api key invalid", "invalid api key",
        "api_key_invalid", "unauthenticated", "invalid_argument: api key",
        "api key not valid"
    ]
    is_auth = any(k in safe_lower for k in auth_indicators)
    if not is_auth and "permission_denied" in safe_lower:
        # Check if permission_denied is due to quota/billing before marking as auth error
        if not any(k in safe_lower for k in ["quota", "bill", "limit", "tier", "exceed"]):
            is_auth = True

    if is_auth:
        return ProviderAuthError("Gemini API key is missing or invalid.")

    # 6. Fallback 429 / resource exhausted
    if code == 429 or "resource_exhausted" in safe_lower or "429" in safe_str:
        return QuotaExhaustedError(
            "Gemini request quota or resource limit exceeded.",
            raw_error=safe_str
        )

    return LLMProviderError(f"LLM generation failed: {safe_str}")


class LLMProvider:
    """
    Abstract interface for LLM providers.
    Ensures our agent is not tightly coupled to OpenAI, Gemini, etc.
    """
    def generate(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Takes conversation history and available tools.
        Returns a dict indicating the LLM's action:
        - {"type": "text", "content": "..."}
        - {"type": "tool_call", "tool_name": "...", "arguments": {...}}
        """
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    """
    Implementation of LLMProvider using Google Gemini API.
    Defaults to gemini-3.8-flash for fast, capable reasoning and tool calling.
    """
    def __init__(self, model_name: Optional[str] = None):
        api_key = get_gemini_api_key()
        if not api_key:
            raise ProviderAuthError("Gemini API key is not configured in environment.")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name or DEFAULT_GENERATION_MODEL
        self.chat = None

    def _send_with_retry(self, content, max_retries: int = 2):
        """
        Sends message to Gemini chat session with intelligent retry:
        - Never retries QuotaExhaustedError (immediate abort without retry loop).
        - Retries transient RateLimitError only if provider advises short delay (<= 5.0s) and attempts remain.
        - Retries ProviderOverloadError with exponential backoff up to max_retries.
        - Raises classified, clean exceptions.
        """
        for attempt in range(max_retries):
            try:
                return self.chat.send_message(content)
            except Exception as e:
                classified = classify_llm_error(e)

                # 1. Quota Exhaustion: NEVER retry
                if isinstance(classified, QuotaExhaustedError):
                    logger.warning("[LLM Quota] Daily quota exhausted. Immediate abort without retries.")
                    raise classified

                # 2. Transient Rate Limit: check provider retry guidance
                if isinstance(classified, RateLimitError):
                    if classified.retry_after and classified.retry_after <= 5.0 and attempt < max_retries - 1:
                        wait_time = classified.retry_after + 0.2
                        logger.info(f"   [LLM Retry] Rate limited. Waiting {wait_time:.1f}s per provider guidance (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise classified

                # 3. Provider Overload (503): backoff retry
                if isinstance(classified, ProviderOverloadError):
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.info(f"   [LLM Retry] Provider overloaded (503). Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise classified

                # All other exceptions: raise immediately
                raise classified

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        last_msg = messages[-1]

        # Initialize a new chat session if this is the start of a new interaction
        if len(messages) == 1 or self.chat is None:
            function_declarations = []
            for t in tools:
                kwargs = {
                    "name": t["name"],
                    "description": t["description"],
                }
                if "parameters" in t:
                    kwargs["parameters"] = t["parameters"]
                fd = types.FunctionDeclaration(**kwargs)
                function_declarations.append(fd)
            
            gemini_tools = [types.Tool(function_declarations=function_declarations)] if function_declarations else None
            config_kwargs: Dict[str, Any] = {
                "tools": gemini_tools,
                "temperature": 0.1
            }
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction

            config = types.GenerateContentConfig(**config_kwargs)
            self.chat = self.client.chats.create(
                model=self.model_name,
                config=config
            )

        # Send the latest message (either user text or tool response part) to Gemini chat session
        if last_msg["role"] == "user":
            response = self._send_with_retry(last_msg["content"])
        elif last_msg["role"] == "tool":
            # Package the Python tool execution result as a FunctionResponse part
            part = types.Part.from_function_response(
                name=last_msg["tool_name"],
                response=last_msg["content"]
            )
            response = self._send_with_retry(part)
        else:
            raise ValueError(f"Unsupported role for sending to chat: {last_msg['role']}")

        # Check if the model requested another tool call
        if response.function_calls:
            fc = response.function_calls[0]
            return {
                "type": "tool_call",
                "tool_name": fc.name,
                "arguments": fc.args or {}
            }
        
        # Safely extract text content from response
        content = response.text
        if not content and response.candidates:
            parts = response.candidates[0].content.parts if response.candidates[0].content else []
            text_parts = [p.text for p in parts if getattr(p, "text", None)]
            if text_parts:
                content = "".join(text_parts)

        return {
            "type": "text",
            "content": content if content else "No text generated."
        }

