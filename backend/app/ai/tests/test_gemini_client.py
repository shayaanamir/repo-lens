import httpx
import pytest

from app.ai.gemini_client import GeminiError, GeminiRateLimitError, generate_content
from app.core.config import settings

_RealAsyncClient = httpx.AsyncClient  # capture before any test patches the name


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _ensure_api_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key-for-tests")


def _patch_client_with_handler(monkeypatch, handler):
    """Swaps httpx.AsyncClient for one that always talks to a
    MockTransport wired to `handler`, regardless of what kwargs
    generate_content() constructs it with."""
    def _fake_async_client(**kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client)


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.anyio
async def test_missing_api_key_raises_immediately(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")

    with pytest.raises(GeminiError, match="not configured"):
        await generate_content("hello")


@pytest.mark.anyio
async def test_successful_response_returns_text(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": "Hello there"}]}}]
        })

    _patch_client_with_handler(monkeypatch, handler)

    result = await generate_content("hi")
    assert result == "Hello there"


@pytest.mark.anyio
async def test_joins_multiple_text_parts(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": "Hello "}, {"text": "there"}]}}]
        })

    _patch_client_with_handler(monkeypatch, handler)

    result = await generate_content("hi")
    assert result == "Hello there"


@pytest.mark.anyio
async def test_429_raises_rate_limit_error_specifically(monkeypatch):
    def handler(request):
        return httpx.Response(429, text="quota exceeded")

    _patch_client_with_handler(monkeypatch, handler)

    with pytest.raises(GeminiRateLimitError):
        await generate_content("hi")


@pytest.mark.anyio
async def test_non_200_raises_generic_gemini_error(monkeypatch):
    def handler(request):
        return httpx.Response(500, text="internal error")

    _patch_client_with_handler(monkeypatch, handler)

    with pytest.raises(GeminiError):
        await generate_content("hi")


@pytest.mark.anyio
async def test_malformed_response_shape_raises_gemini_error(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"unexpected": "shape"})

    _patch_client_with_handler(monkeypatch, handler)

    with pytest.raises(GeminiError, match="Unexpected Gemini response shape"):
        await generate_content("hi")


@pytest.mark.anyio
async def test_empty_text_raises_gemini_error(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": "   "}]}}]
        })

    _patch_client_with_handler(monkeypatch, handler)

    with pytest.raises(GeminiError, match="empty response"):
        await generate_content("hi")


@pytest.mark.anyio
async def test_timeout_raises_gemini_error(monkeypatch):
    def handler(request):
        raise httpx.TimeoutException("timed out", request=request)

    _patch_client_with_handler(monkeypatch, handler)

    with pytest.raises(GeminiError, match="timed out"):
        await generate_content("hi")