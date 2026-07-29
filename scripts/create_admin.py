#!/usr/bin/env python3
"""Legt den ersten Admin an (kein Self-Signup). Gibt das TOTP-Secret + URI aus.

Aufruf:  uv run python scripts/create_admin.py <benutzername> [--role admin|musiker|chor|gast]
Passwort aus $NOTEN_ADMIN_PASSWORD oder interaktiver Eingabe.
"""
from __future__ import annotations

import asyncio
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from app.auth import service  # noqa: E402
from app.config import get_settings  # noqa: E402


async def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Nutzung: create_admin.py <benutzername> [--role <rolle>]")
        raise SystemExit(2)
    username = args[0]
    rolle = args[args.index("--role") + 1] if "--role" in args else "admin"
    password = os.environ.get("NOTEN_ADMIN_PASSWORD") or getpass.getpass("Passwort: ")

    settings = get_settings()
    async with await psycopg.AsyncConnection.connect(
        settings.database_url, autocommit=True, row_factory=dict_row
    ) as conn:
        if await service.get_user_by_name(conn, username):
            print(f"Benutzer '{username}' existiert bereits — abgebrochen.")
            return
        user = await service.create_user(conn, username, password, rolle)

    print("\n✓ Benutzer angelegt")
    print(f"  Benutzername : {user['benutzername']}  (Rolle: {user['rolle']})")
    print(f"  TOTP-Secret  : {user['totp_secret']}")
    print("  Authenticator (URI in App/als QR importieren):")
    print(f"  {user['totp_uri']}\n")


if __name__ == "__main__":
    asyncio.run(main())
