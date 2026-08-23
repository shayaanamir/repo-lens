import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_TIMEOUT_SECONDS = 30.0


class GeminiError(Exception):
    """Raised when a Gemini API call fails for any reason (timeout, HTTP
    error, rate limit, or an unexpected response shape)."""
    pass


class GeminiRateLimitError(GeminiError):
    """Raised specifically on HTTP 429 — distinct from other GeminiErrors
    so callers can tell 'quota exhausted' apart from a generic failure,
    mirroring git_service.py's CloneTimeoutError split."""
    pass


async def generate_content(
    prompt: str,
    model: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """
    Sends a single-turn prompt to the Gemini API and returns the
    generated text. Raises GeminiError (or GeminiRateLimitError) on any
    failure — never returns a partial or garbage string.
    """
    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY is not configured")

    resolved_model = model or settings.gemini_model
    url = f"{GEMINI_API_BASE}/{resolved_model}:generateContent"
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": settings.gemini_api_key,
                },
                json=payload,
            )
    except httpx.TimeoutException as e:
        raise GeminiError(f"Gemini request timed out after {timeout_seconds}s") from e
    except httpx.HTTPError as e:
        raise GeminiError(f"Gemini request failed: {e}") from e

    if response.status_code == 429:
        raise GeminiRateLimitError("Gemini API rate limit / quota exceeded")

    if response.status_code != 200:
        raise GeminiError(f"Gemini API returned {response.status_code}: {response.text[:500]}")

    try:
        data = response.json()
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, ValueError) as e:
        raise GeminiError(f"Unexpected Gemini response shape: {e}") from e

    if not text.strip():
        raise GeminiError("Gemini returned an empty response")

    return text