"""Auth-Kernlogik: Benutzer anlegen, authentifizieren, Sitzungen verwalten.

Session-Store ist DB-gestützt (Tabelle `sitzung`); der Zugriff ist gekapselt,
sodass später auf Redis umgestellt werden kann, ohne Aufrufer zu ändern.
"""
from __future__ import annotations

from typing import Optional

from psycopg import AsyncConnection

from .. import security
from ..config import Settings


async def get_user_by_name(conn: AsyncConnection, username: str) -> Optional[dict]:
    cur = await conn.execute("select * from benutzer where benutzername = %s", (username,))
    return await cur.fetchone()


async def create_user(
    conn: AsyncConnection,
    username: str,
    password: str,
    rolle: str = "gast",
    email: Optional[str] = None,
) -> dict:
    """Legt einen Benutzer an (kein Self-Signup — nur durch Admin/Skript).

    Erzeugt ein TOTP-Secret und gibt es samt Provisioning-URI zurück,
    damit es EINMALIG in die Authenticator-App übernommen werden kann.
    """
    secret = security.new_totp_secret()
    pw_hash = security.hash_password(password)
    cur = await conn.execute(
        """insert into benutzer (benutzername, email, passwort_hash, totp_secret, rolle)
           values (%s, %s, %s, %s, %s)
           returning id, benutzername, rolle""",
        (username, email, pw_hash, secret, rolle),
    )
    row = await cur.fetchone()
    row["totp_secret"] = secret
    row["totp_uri"] = security.totp_uri(secret, username)
    return row


async def _register_failure(conn: AsyncConnection, user: dict, settings: Settings) -> None:
    n = user["fehlversuche"] + 1
    if n >= settings.max_login_attempts:
        await conn.execute(
            "update benutzer set fehlversuche = 0, "
            "gesperrt_bis = now() + make_interval(mins => %s) where id = %s",
            (settings.lockout_minutes, user["id"]),
        )
    else:
        await conn.execute(
            "update benutzer set fehlversuche = %s where id = %s", (n, user["id"])
        )


async def authenticate(
    conn: AsyncConnection, username: str, password: str, totp: str, settings: Settings
) -> tuple[Optional[dict], Optional[str]]:
    """Prüft Passwort UND TOTP (Pflicht). Rückgabe: (user, fehler_code).

    fehler_code: 'locked' (gesperrt), 'invalid' (falsch/unbekannt/inaktiv).
    Bewusst generische Fehler gegen Benutzer-Enumeration.
    """
    user = await get_user_by_name(conn, username)
    if not user or not user["aktiv"]:
        security.verify_password(security.DUMMY_HASH, password)  # Zeit angleichen (Anti-Enumeration)
        return None, "invalid"
    if user["gesperrt_bis"] is not None:
        cur = await conn.execute("select %s > now() as locked", (user["gesperrt_bis"],))
        if (await cur.fetchone())["locked"]:
            return None, "locked"
    if not security.verify_password(user["passwort_hash"], password):
        await _register_failure(conn, user, settings)
        return None, "invalid"
    # TOTP nur, wenn global Pflicht UND für diesen Benutzer aktiviert (Admin kann pro Nutzer abschalten)
    if settings.totp_pflicht and user["totp_aktiviert"]:
        ok, new_step = security.verify_totp(
            user["totp_secret"], totp, user["totp_last_step"], settings.totp_valid_window
        )
        if not ok:
            await _register_failure(conn, user, settings)
            return None, "invalid"
        await conn.execute(
            "update benutzer set fehlversuche = 0, gesperrt_bis = null, totp_last_step = %s where id = %s",
            (new_step, user["id"]),
        )
    else:
        # 2FA (global oder für diesen Nutzer) deaktiviert — nur Passwort
        await conn.execute(
            "update benutzer set fehlversuche = 0, gesperrt_bis = null where id = %s",
            (user["id"],),
        )
    return user, None


# --- Sitzungen ---
async def create_session(
    conn: AsyncConnection,
    user_id,
    settings: Settings,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> str:
    token = security.new_session_token()
    await conn.execute(
        """insert into sitzung (token_hash, benutzer_id, expires_at, user_agent, ip)
           values (%s, %s, now() + make_interval(secs => %s), %s, %s)""",
        (security.token_hash(token), user_id, settings.session_ttl_seconds, user_agent, ip),
    )
    return token


async def get_session_user(conn: AsyncConnection, token: str) -> Optional[dict]:
    th = security.token_hash(token)
    cur = await conn.execute(
        """select b.* from sitzung s join benutzer b on b.id = s.benutzer_id
           where s.token_hash = %s and s.expires_at > now() and b.aktiv""",
        (th,),
    )
    user = await cur.fetchone()
    if user:
        await conn.execute("update sitzung set last_seen = now() where token_hash = %s", (th,))
    return user


async def destroy_session(conn: AsyncConnection, token: str) -> None:
    await conn.execute(
        "delete from sitzung where token_hash = %s", (security.token_hash(token),)
    )


async def change_password(conn: AsyncConnection, benutzer_id, altes: str, neues: str) -> bool:
    cur = await conn.execute("select passwort_hash from benutzer where id = %s", (benutzer_id,))
    row = await cur.fetchone()
    if not row or not security.verify_password(row["passwort_hash"], altes):
        return False
    await conn.execute(
        "update benutzer set passwort_hash = %s where id = %s",
        (security.hash_password(neues), benutzer_id),
    )
    return True


async def list_users(conn: AsyncConnection) -> list[dict]:
    cur = await conn.execute(
        "select id, benutzername, email, rolle, aktiv, totp_aktiviert, created_at "
        "from benutzer order by benutzername"
    )
    return await cur.fetchall()


async def list_user_namen(conn: AsyncConnection) -> list[dict]:
    """Nur id + Benutzername aktiver Konten — für Auswahl-Picker (musiker-Rolle)."""
    cur = await conn.execute(
        "select id, benutzername from benutzer where aktiv order by benutzername"
    )
    return await cur.fetchall()


async def get_user(conn: AsyncConnection, benutzer_id) -> dict | None:
    cur = await conn.execute(
        "select id, benutzername, email, rolle, aktiv, totp_aktiviert from benutzer where id = %s",
        (benutzer_id,),
    )
    return await cur.fetchone()


async def count_active_admins(conn: AsyncConnection) -> int:
    cur = await conn.execute(
        "select count(*)::int as n from benutzer where rolle = 'admin' and aktiv"
    )
    return (await cur.fetchone())["n"]


async def set_user(conn: AsyncConnection, benutzer_id, fields: dict) -> dict | None:
    fields = {
        k: v for k, v in fields.items() if k in ("rolle", "aktiv", "benutzername", "email") and v is not None
    }
    if fields:
        sets = ", ".join(f"{k} = %s" for k in fields)
        await conn.execute(
            f"update benutzer set {sets} where id = %s", (*fields.values(), benutzer_id)
        )
    return await get_user(conn, benutzer_id)


async def admin_set_password(conn: AsyncConnection, benutzer_id, neues: str) -> bool:
    """Admin setzt ein neues Passwort (ohne altes) und beendet alle Sessions des Nutzers."""
    cur = await conn.execute(
        "update benutzer set passwort_hash = %s where id = %s",
        (security.hash_password(neues), benutzer_id),
    )
    if cur.rowcount == 0:
        return False
    await conn.execute("delete from sitzung where benutzer_id = %s", (benutzer_id,))
    return True


async def set_2fa(conn: AsyncConnection, benutzer_id, aktiv: bool) -> dict | None:
    """2FA pro Nutzer an-/ausschalten. Beim Einschalten neues Secret + Enrollment-URI."""
    if aktiv:
        secret = security.new_totp_secret()
        cur = await conn.execute(
            "update benutzer set totp_secret = %s, totp_aktiviert = true, totp_last_step = 0 "
            "where id = %s returning benutzername",
            (secret, benutzer_id),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "benutzername": row["benutzername"],
            "totp_aktiviert": True,
            "totp_uri": security.totp_uri(secret, row["benutzername"]),
        }
    cur = await conn.execute(
        "update benutzer set totp_aktiviert = false where id = %s returning benutzername",
        (benutzer_id,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return {"benutzername": row["benutzername"], "totp_aktiviert": False, "totp_uri": None}


async def delete_user(conn: AsyncConnection, benutzer_id) -> bool:
    cur = await conn.execute("delete from benutzer where id = %s", (benutzer_id,))
    return cur.rowcount > 0
