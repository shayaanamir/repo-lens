class AIUnavailableError(Exception):
    """Raised when the chat/explain/summarize pipeline can't produce a
    result because Gemini is unavailable or rate-limited. Routers catch
    this and return a clean 503 instead of a stack trace — PROJECT.md
    §6.2, 'AI is an enhancement'."""
    pass