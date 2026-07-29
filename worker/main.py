"""Worker-Loop: nimmt offene Jobs aus der `job`-Tabelle und arbeitet sie ab.

Läuft im eigenen Container (mit music21 & Co.), getrennt von der schlanken API. Nimmt einen
Job atomar per FOR UPDATE SKIP LOCKED (mehrere Worker möglich), ruft den Handler und schreibt
Fortschritt zurück. Das Frontend pollt GET /api/jobs/{id}.
"""
from __future__ import annotations

import os
import time
import traceback

import psycopg
from psycopg.rows import dict_row

from . import handlers

POLL_SEC = float(os.environ.get("NOTEN_WORKER_POLL", "5"))


def _connect():
    return psycopg.connect(os.environ["NOTEN_DATABASE_URL"], autocommit=True, row_factory=dict_row)


class JobCtx:
    """Fortschritts-API für Handler."""

    def __init__(self, conn, job_id):
        self.conn = conn
        self.job_id = job_id

    def fortschritt(self, fertig=None, gesamt=None, aktuell=None, log_zeile=None):
        sets, vals = [], []
        if fertig is not None:
            sets.append("fortschritt = %s")
            vals.append(fertig)
        if gesamt is not None:
            sets.append("gesamt = %s")
            vals.append(gesamt)
        if aktuell is not None:
            sets.append("aktuell = %s")
            vals.append(aktuell)
        if sets:
            sets.append("updated_at = now()")
            self.conn.execute(f"update job set {', '.join(sets)} where id = %s", (*vals, self.job_id))
        if log_zeile:
            self.conn.execute(
                "update job set log = coalesce(log, '') || %s where id = %s", (log_zeile + "\n", self.job_id)
            )

    def abgebrochen(self) -> bool:
        cur = self.conn.execute("select status from job where id = %s", (self.job_id,))
        r = cur.fetchone()
        return (not r) or r["status"] == "abgebrochen"


def _naechster_job(conn):
    cur = conn.execute(
        """update job set status = 'laeuft', updated_at = now()
           where id = (select id from job where status = 'offen'
                       order by created_at for update skip locked limit 1)
           returning *"""
    )
    return cur.fetchone()


def run_once(conn) -> bool:
    job = _naechster_job(conn)
    if not job:
        return False
    ctx = JobCtx(conn, job["id"])
    handler = handlers.REGISTRY.get(job["typ"])
    try:
        if handler is None:
            raise RuntimeError(f"kein Handler für Typ '{job['typ']}'")
        handler(conn, job, ctx)
        conn.execute(
            "update job set status = 'fertig', updated_at = now() where id = %s and status = 'laeuft'",
            (job["id"],),
        )
    except Exception as exc:  # noqa: BLE001
        conn.execute(
            "update job set status = 'fehler', aktuell = %s, log = coalesce(log,'') || %s, updated_at = now() where id = %s",
            (str(exc)[:200], "FEHLER: " + traceback.format_exc()[-1500:], job["id"]),
        )
    return True


def main():
    print("[worker] gestartet, poll alle", POLL_SEC, "s")
    while True:
        try:
            with _connect() as conn:
                while run_once(conn):
                    pass
        except Exception as exc:  # noqa: BLE001 — Worker soll durchlaufen
            print("[worker] Loop-Fehler:", exc)
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
