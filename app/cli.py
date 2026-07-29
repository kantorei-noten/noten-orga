"""CLI-Kommandos — im Container:  python -m app.cli <befehl> …

create-admin <benutzername> [--email …] [--passwort …]
    Legt den ersten Admin an (kein Self-Signup) und zeigt die 2FA-Provisioning-URI,
    die EINMALIG in die Authenticator-App übernommen wird. Das Passwort kommt aus
    --passwort, sonst der Umgebung NOTEN_ADMIN_PASSWORD, sonst interaktiver Abfrage.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import psycopg
from psycopg.rows import dict_row

from .auth import service as auth_service
from .config import get_settings


async def _create_admin(benutzername: str, passwort: str, email: str | None) -> int:
    settings = get_settings()
    async with await psycopg.AsyncConnection.connect(
        settings.database_url, autocommit=True, row_factory=dict_row
    ) as conn:
        cur = await conn.execute("select 1 from benutzer where benutzername = %s", (benutzername,))
        if await cur.fetchone():
            print(f"Benutzer '{benutzername}' existiert bereits — nichts geändert.", file=sys.stderr)
            return 1
        try:
            row = await auth_service.create_user(conn, benutzername, passwort, "admin", email)
        except psycopg.errors.UniqueViolation:
            print("Benutzername oder E-Mail existiert bereits.", file=sys.stderr)
            return 1
    print(f"Admin '{benutzername}' angelegt.")
    print("2FA für die Authenticator-App (einmalig einscannen):")
    print(f"  {row['totp_uri']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ca = sub.add_parser("create-admin", help="Ersten Admin-Benutzer anlegen")
    ca.add_argument("benutzername")
    ca.add_argument("--email", default=None)
    ca.add_argument("--passwort", default=None, help="sonst NOTEN_ADMIN_PASSWORD oder interaktive Abfrage")
    args = ap.parse_args(argv)

    if args.cmd == "create-admin":
        pw = args.passwort or os.environ.get("NOTEN_ADMIN_PASSWORD")
        if not pw:
            import getpass

            pw = getpass.getpass(f"Passwort für Admin '{args.benutzername}': ")
        if len(pw) < 8:
            print("Passwort muss mindestens 8 Zeichen haben.", file=sys.stderr)
            return 2
        return asyncio.run(_create_admin(args.benutzername, pw, args.email))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
