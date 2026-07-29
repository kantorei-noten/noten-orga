"""Auth-Endpunkte: Login (Passwort + Pflicht-TOTP), Logout, aktueller Benutzer."""
from __future__ import annotations

import ipaddress
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..auth import service
from ..auth.deps import current_user
from ..config import get_settings
from ..db import get_conn

router = APIRouter(prefix="/auth", tags=["auth"])

# Einfaches Per-IP-Login-Limit (zusätzlich zu Konto-Lockout + fail2ban): begrenzt
# Brute-Force und den gezielten Lockout-DoS eines einzelnen Kontos.
_login_hits: dict[str, list[float]] = {}
_LOGIN_MAX = 20
_LOGIN_WINDOW = 300.0  # 5 min


# Netze, aus denen ein X-Forwarded-For überhaupt geglaubt wird: der eigene Reverse-Proxy
# (Docker-Netz, 127.0.0.1 beim Betrieb per systemd). Kommt die Verbindung von woanders,
# steht die App direkt im Netz — dann ist der Header frei erfundenes Client-Material.
_PROXY_NETZE = tuple(
    ipaddress.ip_network(n)
    for n in ("127.0.0.0/8", "::1/128", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)


def _client_ip(request: Request) -> str:
    """Client-Adresse fürs Rate-Limit — nicht fälschbar.

    Caddy & Co. HÄNGEN an X-Forwarded-For an, statt ihn zu ersetzen: Ein Angreifer, der
    'X-Forwarded-For: 1.2.3.4' mitschickt, erzeugt '1.2.3.4, <echte IP>'. Der erste Eintrag
    ist also frei wählbar — mit ihm ließe sich das Login-Limit beliebig umgehen. Darum zählt
    hier der LETZTE Eintrag (den der eigene Proxy angehängt hat), und auch nur, wenn die
    Verbindung tatsächlich von einem Proxy im internen Netz kommt.
    """
    peer = request.client.host if request.client else None
    if peer is None or _ist_proxy(peer):
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[-1].strip()
    return peer or "?"


def _ist_proxy(host: str) -> bool:
    try:
        return any(ipaddress.ip_address(host) in netz for netz in _PROXY_NETZE)
    except ValueError:  # Unix-Socket o. Ä. — kein IP-Peer, also lokal
        return True


def _rate_ok(ip: str) -> bool:
    now = time.monotonic()
    hits = [t for t in _login_hits.get(ip, []) if now - t < _LOGIN_WINDOW]
    hits.append(now)
    _login_hits[ip] = hits
    if len(_login_hits) > 5000:  # Speicher deckeln
        _login_hits.clear()
    return len(hits) <= _LOGIN_MAX


class LoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    totp: str = Field(default="", max_length=8)  # bei deaktivierter 2FA optional


@router.get("/config")
async def config():
    """Öffentlich: sagt dem Login-Formular, ob ein 2FA-Code nötig ist."""
    return {"totp_pflicht": get_settings().totp_pflicht}


@router.post("/login")
async def login(data: LoginIn, request: Request, response: Response, conn=Depends(get_conn)):
    settings = get_settings()
    ip = _client_ip(request)
    if settings.environment != "test" and not _rate_ok(ip):
        raise HTTPException(status_code=429, detail="Zu viele Anmeldeversuche. Bitte kurz warten.")
    user, err = await service.authenticate(
        conn, data.username, data.password, data.totp, settings
    )
    # Einheitliche Antwort (auch bei Sperre) — keine Benutzer-Enumeration über den Status
    if err:
        raise HTTPException(status_code=401, detail="Anmeldung fehlgeschlagen")
    token = await service.create_session(
        conn,
        user["id"],
        settings,
        request.headers.get("user-agent"),
        ip,
    )
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/",
    )
    return {"benutzername": user["benutzername"], "rolle": user["rolle"]}


@router.post("/logout")
async def logout(request: Request, response: Response, conn=Depends(get_conn)):
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await service.destroy_session(conn, token)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"status": "ok"}


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return {
        "id": str(user["id"]),
        "benutzername": user["benutzername"],
        "rolle": user["rolle"],
    }


class PasswortIn(BaseModel):
    altes_passwort: str = Field(min_length=1)
    neues_passwort: str = Field(min_length=8, max_length=200)


@router.post("/passwort")
async def passwort_aendern(data: PasswortIn, user: dict = Depends(current_user), conn=Depends(get_conn)):
    if not await service.change_password(conn, user["id"], data.altes_passwort, data.neues_passwort):
        raise HTTPException(status_code=400, detail="Aktuelles Passwort ist falsch")
    return {"status": "ok"}
