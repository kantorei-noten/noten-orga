#!/usr/bin/env python3
"""Import kirchenrelevanter Noten aus dem Mutopia Project in Noten-Orga.

Mutopia (mutopiaproject.org) liefert LilyPond-gesetzte, gemeinfreie/CC-Noten als
PDF/MIDI/.ly. Für Noten-Orga hängen wir die **A4-PDF** an (kein MusicXML vorhanden).

Für jedes Stück:
  1. Metadaten aus der Suchtabelle (make-table.cgi) parsen
  2. POST /api/werke  -> Werk+Fassung+Ausgabe (liefert ausgabe_id)
  3. A4-PDF von Mutopia laden -> POST /api/dateien (art=scan_pdf, sha256-Dedup, Thumbnail)

Umfang (--scope):
  church = Orgel + Hymn + Gospel (~294)
  all    = church + alle Voice-Werke (~575)   [Default]

Idempotent: bereits vorhandene Werke (Titel+Komponist) werden übersprungen.

Voraussetzungen:  pip install requests
Beispiele:
  NOTEN_USER=admin NOTEN_PASS=... python scripts/import_mutopia.py \
      --base-url https://noten.example.org --dry-run --limit 8
  NOTEN_USER=admin NOTEN_PASS=... python scripts/import_mutopia.py \
      --base-url https://noten.example.org --scope all
"""
from __future__ import annotations

import argparse
import csv
import html as _html
import io
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from getpass import getpass

import requests

MUT = "https://www.mutopiaproject.org"
TABLE = MUT + "/cgibin/make-table.cgi"
UA = "noten-orga-mutopia-import/1.0 (Kirchenmusik-Archiv)"

SCOPES = {
    "church": [{"Instrument": "Organ"}, {"Style": "Hymn"}, {"Style": "Gospel"}],
    "all": [{"Instrument": "Organ"}, {"Instrument": "Voice"}, {"Style": "Hymn"}, {"Style": "Gospel"}],
}


# --------------------------------------------------------------------------- #
# Mutopia-Crawl                                                               #
# --------------------------------------------------------------------------- #
def _txt(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _clean_composer(s: str) -> str:
    """'by J. S. Bach (1685–1750)' -> 'J. S. Bach' (Präfix + Lebensdaten weg)."""
    s = re.sub(r"^by\s+", "", (s or "").strip())
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    return s.strip()


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "replace")


def parse_piece(block: str) -> dict | None:
    mid = re.search(r"piece-info\.cgi\?id=(\d+)", block)
    if not mid:
        return None
    texts = [_txt(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", block, re.S)]
    if len(texts) < 4 or not texts[0]:
        return None
    title, composer = texts[0], _clean_composer(texts[1])
    instr = year = style = ""
    for i, x in enumerate(texts):
        if x.lower().startswith("for "):
            instr = x[4:].strip()
            year = texts[i + 1] if i + 1 < len(texts) else ""
            style = texts[i + 2] if i + 2 < len(texts) else ""
            break
    lic = re.search(r'legal\.html#[^"]*">([^<]*)</a>', block)
    a4 = re.search(r"(https://[^\"]*-a4\.pdf)", block)
    let = re.search(r"(https://[^\"]*-let\.pdf)", block)
    return {
        "id": mid.group(1),
        "title": title,
        "composer": composer,
        "instrument": instr,
        "year": year,
        "style": style,
        "license": _txt(lic.group(1)) if lic else "",
        "pdf": a4.group(1) if a4 else (let.group(1) if let else None),
    }


def crawl_filter(filt: dict, sleep: float = 0.3, cap: int = 3000) -> dict:
    """Alle Stücke eines Filters (paginiert über startat). Rückgabe id->piece."""
    out: dict[str, dict] = {}
    start = 0
    while start < cap:
        params = {
            "startat": str(start),
            "Composer": "",
            "Instrument": filt.get("Instrument", ""),
            "Style": filt.get("Style", ""),
            "collection": "",
            "preview": "",
        }
        html = _get(TABLE + "?" + urllib.parse.urlencode(params))
        blocks = re.split(r'<table class="table-bordered result-table">', html)[1:]
        for b in blocks:
            p = parse_piece(b)
            if p and p["id"] not in out:
                out[p["id"]] = p
        ids_here = set(re.findall(r"piece-info\.cgi\?id=(\d+)", html))
        if len(ids_here) < 10:
            break
        start += 10
        time.sleep(sleep)
    return out


def sammle_stuecke(scope: str, sleep: float) -> list[dict]:
    alle: dict[str, dict] = {}
    for filt in SCOPES[scope]:
        teil = crawl_filter(filt, sleep=sleep)
        for pid, p in teil.items():
            alle.setdefault(pid, p)
        print(f"  [{filt}] -> {len(teil)} (kumuliert {len(alle)})")
    return sorted(alle.values(), key=lambda p: (p["composer"].lower(), p["title"].lower()))


# --------------------------------------------------------------------------- #
# Metadaten-Mapping                                                           #
# --------------------------------------------------------------------------- #
def map_besetzung(instr: str) -> str | None:
    s = instr or ""
    if "SATB" in s:
        return "SATB"
    if "SSA" in s or "SSAA" in s:
        return "SSA"
    if "TTBB" in s or "TTB" in s:
        return "TTBB"
    if "SAB" in s:
        return "SAB"
    if re.search(r"\(SA\b", s):
        return "SA"
    if "Organ" in s or "Harmonium" in s:
        return "Orgel"
    if "Brass" in s:
        return "Bläser"
    if "Voice" in s:
        return "Kantor"
    return None


def map_gattung(instr: str, style: str) -> str | None:
    if "Organ" in instr:
        return "Orgelwerk"
    if style == "Hymn":
        return "Choral/Hymne"
    if style == "Gospel":
        return "Gospel"
    if "SATB" in instr or "SAB" in instr or "SSA" in instr or "TTBB" in instr:
        return "Chorwerk"
    if "Voice" in instr:
        return "Vokalwerk"
    return style or None


def parse_year(y: str) -> int | None:
    m = re.search(r"\b(1[0-9]{3}|20[0-2][0-9])\b", y or "")
    return int(m.group(1)) if m else None


def tags_for(p: dict) -> list[str]:
    instr = p["instrument"]
    tags = ["Mutopia"]
    if p["style"]:
        tags.append(p["style"])
    if "Organ" in instr:
        tags.append("Orgel")
    elif any(v in instr for v in ("SATB", "SAB", "SSA", "TTBB")):
        tags.append("Chor")
    elif "Voice" in instr:
        tags.append("Gesang")
    elif "Brass" in instr:
        tags.append("Bläser")
    if p["license"]:
        tags.append(p["license"])
    return tags


def safe_filename(title: str) -> str:
    base = re.sub(r"[^\w\-. ]", "_", title, flags=re.UNICODE).strip().strip(".") or "mutopia"
    return f"{base[:80]}.pdf"


def download_pdf(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
    if not data.startswith(b"%PDF"):
        raise ValueError("kein gültiges PDF")
    return data


# --------------------------------------------------------------------------- #
# Noten-Orga-API                                                              #
# --------------------------------------------------------------------------- #
class NotenClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "noten-orga-mutopia-import/1.0"

    def login(self, user: str, password: str, totp: str = "") -> None:
        cfg = self.s.get(f"{self.base}/api/auth/config", timeout=30)
        cfg.raise_for_status()
        if cfg.json().get("totp_pflicht") and not totp:
            totp = os.environ.get("NOTEN_TOTP", "") or input("TOTP-Code: ").strip()
        r = self.s.post(
            f"{self.base}/api/auth/login",
            json={"username": user, "password": password, "totp": totp},
            timeout=30,
        )
        if r.status_code != 200:
            sys.exit(f"Login fehlgeschlagen ({r.status_code}): {r.text[:200]}")

    def valid_besetzungen(self) -> set[str]:
        try:
            r = self.s.get(f"{self.base}/api/besetzungen", timeout=30)
            r.raise_for_status()
            return {row["kuerzel"] for row in r.json()}
        except Exception:
            return set()

    def existing_keys(self) -> set[tuple[str, str]]:
        r = self.s.get(f"{self.base}/api/werke/export-csv", timeout=120)
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";")
        keys = set()
        for row in reader:
            t = (row.get("titel") or "").strip().lower()
            k = (row.get("komponist") or "").strip().lower()
            if t:
                keys.add((t, k))
        return keys

    def create_werk(self, payload: dict) -> str:
        r = self.s.post(f"{self.base}/api/werke", json=payload, timeout=60)
        r.raise_for_status()
        ausgaben = r.json().get("ausgaben") or []
        if not ausgaben:
            raise RuntimeError("Werk ohne Ausgabe")
        return ausgaben[0]["id"]

    def attach_pdf(self, ausgabe_id: str, filename: str, pdf: bytes, art: str) -> dict:
        files = {"file": (filename, pdf, "application/pdf")}
        r = self.s.post(
            f"{self.base}/api/dateien",
            data={"ausgabe_id": ausgabe_id, "art": art},
            files=files,
            timeout=180,
        )
        r.raise_for_status()
        return r.json()


# --------------------------------------------------------------------------- #
# main                                                                        #
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="Mutopia-Noten in Noten-Orga importieren")
    ap.add_argument("--base-url", default=os.environ.get("NOTEN_BASE_URL", "http://127.0.0.1:8001"))
    ap.add_argument("--user", default=os.environ.get("NOTEN_USER"))
    ap.add_argument("--password", default=os.environ.get("NOTEN_PASS"))
    ap.add_argument("--scope", choices=["church", "all"], default="all")
    ap.add_argument("--limit", type=int, default=0, help="max. Stücke (0 = alle)")
    ap.add_argument("--sleep", type=float, default=0.5, help="Pause zwischen PDF-Downloads (höflich zu Mutopia)")
    ap.add_argument("--art", default="scan_pdf")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Sammle Mutopia-Stücke (scope={args.scope}) …")
    stuecke = sammle_stuecke(args.scope, sleep=0.3)
    if args.limit:
        stuecke = stuecke[: args.limit]
    print(f"-> {len(stuecke)} Stücke zu prüfen.\n")

    client = None
    existing: set[tuple[str, str]] = set()
    allowed_bes: set[str] = set()
    if not args.dry_run:
        if not args.user:
            args.user = input("Benutzer: ").strip()
        if not args.password:
            args.password = getpass("Passwort: ")
        client = NotenClient(args.base_url)
        client.login(args.user, args.password, os.environ.get("NOTEN_TOTP", ""))
        existing = client.existing_keys()
        allowed_bes = client.valid_besetzungen()
        print(f"[i] {len(existing)} bestehende Werke; {len(allowed_bes)} Besetzungs-Kürzel.\n")

    created = skipped = failed = nopdf = 0
    for p in stuecke:
        titel = p["title"].strip()
        komponist = p["composer"].strip() or None
        key = (titel.lower(), (komponist or "").lower())
        if key in existing:
            skipped += 1
            continue

        besetzung = map_besetzung(p["instrument"])
        if besetzung and allowed_bes and besetzung not in allowed_bes:
            besetzung = None
        tags = tags_for(p)
        if besetzung is None and p["instrument"]:
            tags.append(p["instrument"])  # Rohbesetzung als Tag sichern
        payload = {
            "titel": titel,
            "komponist": komponist,
            "gattung": map_gattung(p["instrument"], p["style"]),
            "sprache": None,
            "besetzung": besetzung,
            "entstehungsjahr": parse_year(p["year"]),
            "notiz": (
                f"Quelle: Mutopia Project (LilyPond-Satz), PDF. Stil: {p['style'] or '—'}. "
                f"Lizenz: {p['license'] or '—'}. Instrument: {p['instrument'] or '—'}. "
                f"Mutopia-ID {p['id']}. {p['pdf'] or ''}"
            ).strip(),
            "tags": tags,
        }

        if args.dry_run:
            print(f"  + {titel[:42]:42} | {komponist or '—':22} | {p['style']:10} | "
                  f"bes={besetzung or '—':5} | {p['year'][:8]:8} | pdf={'ja' if p['pdf'] else 'NEIN'}")
            existing.add(key)
            created += 1
            continue

        if not p["pdf"]:
            nopdf += 1
            print(f"  ~ ohne PDF, übersprungen: {titel}")
            continue
        try:
            pdf = download_pdf(p["pdf"])
            ausgabe_id = client.create_werk(payload)
            res = client.attach_pdf(ausgabe_id, safe_filename(titel), pdf, args.art)
            existing.add(key)
            created += 1
            flag = "neu" if res.get("neu") else "dedup"
            print(f"  + {titel[:46]:46} -> {res['seiten'] or '?'}S · {flag} ({len(pdf)//1024}KB)")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            msg = str(exc)
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                msg = f"{exc.response.status_code}: {exc.response.text[:140]}"
            print(f"  ! FEHLER {titel[:40]}: {msg}")
        time.sleep(args.sleep)

    print(f"\nFertig. angelegt={created}  übersprungen={skipped}  ohne_pdf={nopdf}  fehler={failed}"
          + ("  (Trockenlauf)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
