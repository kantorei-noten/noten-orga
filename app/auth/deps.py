"""FastAPI-Dependencies für Authentifizierung & Autorisierung (fail-closed)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from ..config import get_settings
from ..db import get_conn
from . import service


async def current_user(request: Request, conn=Depends(get_conn)) -> dict:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Nicht angemeldet")
    user = await service.get_session_user(conn, token)
    if not user:
        raise HTTPException(status_code=401, detail="Sitzung ungültig oder abgelaufen")
    return user


def require_role(*roles: str):
    """Erlaubt die angegebenen Rollen; Admin darf immer (Superuser)."""

    async def dependency(user: dict = Depends(current_user)) -> dict:
        if user["rolle"] != "admin" and user["rolle"] not in roles:
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
        return user

    return dependency
