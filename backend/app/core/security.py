import hmac

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Guards destructive endpoints. With no ADMIN_TOKEN configured (local
    dev) it lets everything through."""
    if not settings.admin_token:
        return
    supplied = credentials.credentials.encode() if credentials else b""
    if not hmac.compare_digest(supplied, settings.admin_token.encode()):
        raise HTTPException(
            status_code=403,
            detail="Deleting repositories is disabled on this deployment",
        )