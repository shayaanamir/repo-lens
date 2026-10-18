import uuid

from fastapi import Header, HTTPException


async def get_visitor_id(x_visitor_id: str | None = Header(default=None)) -> uuid.UUID:
    """Anonymous per-browser identity. Not security: it only decides whose
    list a repository appears in."""
    if not x_visitor_id:
        raise HTTPException(status_code=400, detail="Missing X-Visitor-Id header")
    try:
        return uuid.UUID(x_visitor_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Visitor-Id header") from None