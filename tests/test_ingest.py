import pymupdf
import pyotp
import pytest

from app.auth import service as auth_service
from app.config import get_settings
from app.ingest import service as ingest_service
from app.ingest.validation import ValidationError

VALID_MUSICXML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<score-partwise version="3.1"><part-list>'
    b'<score-part id="P1"><part-name>Orgel</part-name></score-part></part-list>'
    b'<part id="P1"><measure number="1">'
    b"<note><pitch><step>C</step><octave>4</octave></pitch>"
    b"<duration>4</duration><type>whole</type></note></measure></part></score-partwise>"
)

XXE_XML = (
    b'<?xml version="1.0"?>'
    b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
    b"<score-partwise>&xxe;</score-partwise>"
)


def _pdf_bytes(pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Seite {i + 1}")
    return doc.tobytes()


async def _make_ausgabe(conn) -> str:
    cur = await conn.execute("insert into werk (titel) values ('Testwerk') returning id")
    werk = (await cur.fetchone())["id"]
    cur = await conn.execute("insert into fassung (werk_id) values (%s) returning id", (werk,))
    fassung = (await cur.fetchone())["id"]
    cur = await conn.execute(
        "insert into ausgabe (fassung_id) values (%s) returning id", (fassung,)
    )
    return (await cur.fetchone())["id"]


async def _login(client, conn, name="uploader", rolle="musiker"):
    await conn.execute("delete from benutzer where benutzername = %s", (name,))
    u = await auth_service.create_user(conn, name, "Geheim1234!", rolle)
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login",
        json={"username": name, "password": "Geheim1234!", "totp": code},
    )
    assert r.status_code == 200


# --- Service-Ebene: Validierung & Dedup ---
async def test_pdf_ingest_creates_thumbnail(conn):
    settings = get_settings()
    ausgabe = await _make_ausgabe(conn)
    datei, created = await ingest_service.ingest_file(
        conn, settings, ausgabe, "scan_pdf", "scan.pdf", _pdf_bytes(2)
    )
    assert created is True
    assert datei["seiten"] == 2
    assert datei["art"] == "scan_pdf"
    assert datei["thumb_pfad"]  # Vorschau erzeugt


async def test_dedup_same_bytes(conn):
    settings = get_settings()
    ausgabe = await _make_ausgabe(conn)
    pdf = _pdf_bytes(1)
    d1, c1 = await ingest_service.ingest_file(conn, settings, ausgabe, "scan_pdf", "a.pdf", pdf)
    d2, c2 = await ingest_service.ingest_file(conn, settings, ausgabe, "scan_pdf", "a.pdf", pdf)
    assert c1 is True and c2 is False
    assert d1["id"] == d2["id"]


async def test_reject_non_whitelisted(conn):
    settings = get_settings()
    ausgabe = await _make_ausgabe(conn)
    with pytest.raises(ValidationError):
        await ingest_service.ingest_file(
            conn, settings, ausgabe, "scan_pdf", "evil.exe", b"MZ\x90\x00 kein PDF"
        )


async def test_reject_pdf_active_content(conn):
    settings = get_settings()
    ausgabe = await _make_ausgabe(conn)
    with pytest.raises(ValidationError):
        await ingest_service.ingest_file(
            conn, settings, ausgabe, "scan_pdf", "evil.pdf", b"%PDF-1.4\n/JavaScript (app.alert(1))\n%%EOF"
        )


async def test_reject_xxe(conn):
    settings = get_settings()
    ausgabe = await _make_ausgabe(conn)
    with pytest.raises(ValidationError):
        await ingest_service.ingest_file(
            conn, settings, ausgabe, "scan_pdf", "boese.musicxml", XXE_XML
        )


async def test_accept_valid_musicxml(conn):
    settings = get_settings()
    ausgabe = await _make_ausgabe(conn)
    datei, created = await ingest_service.ingest_file(
        conn, settings, ausgabe, "scan_pdf", "stueck.musicxml", VALID_MUSICXML
    )
    assert created is True
    assert datei["art"] == "musicxml"


# --- Endpunkt-Ebene: Auth + Multipart + Rolle ---
async def test_upload_endpoint(client, conn):
    await _login(client, conn)
    ausgabe = await _make_ausgabe(conn)
    files = {"file": ("scan.pdf", _pdf_bytes(3), "application/pdf")}
    r = await client.post(
        "/api/dateien", files=files, data={"ausgabe_id": str(ausgabe), "art": "scan_pdf"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["seiten"] == 3
    assert body["hat_vorschau"] is True
    # Vorschau abrufbar
    thumb = await client.get(f"/api/dateien/{body['id']}/thumbnail")
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/webp"


async def test_get_werk_liefert_original_name(client, conn):
    # Regression: get_werk muss original_name je Datei liefern, sonst zeigen
    # Werk-Ansicht + Setlisten-Blattauswahl nur generisch "Blatt N".
    await _login(client, conn, name="onametest")
    werk = (await client.post("/api/werke", json={"titel": "Motette"})).json()
    ausgabe_id = werk["ausgaben"][0]["id"]
    up = await client.post(
        "/api/dateien",
        files={"file": ("Sopran.pdf", _pdf_bytes(1), "application/pdf")},
        data={"ausgabe_id": str(ausgabe_id), "art": "scan_pdf"},
    )
    assert up.status_code == 200, up.text
    detail = (await client.get(f"/api/werke/{werk['id']}")).json()
    datei = detail["ausgaben"][0]["dateien"][0]
    assert datei["original_name"] == "Sopran.pdf"


def _pdf_mit_text(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontsize=14)
    return doc.tobytes()


async def test_liedtext_extraktion_und_speichern(client, conn):
    await _login(client, conn, name="lyricuser")
    werk = (await client.post("/api/werke", json={"titel": "Kyrie"})).json()
    ausgabe_id = werk["ausgaben"][0]["id"]
    await client.post(
        "/api/dateien",
        files={"file": ("coro.pdf", _pdf_mit_text("Kyrie eleison Christe eleison"), "application/pdf")},
        data={"ausgabe_id": str(ausgabe_id), "art": "scan_pdf"},
    )
    # Extraktion liefert einen Vorschlag (kein Auto-Speichern)
    r = await client.post(f"/api/werke/{werk['id']}/liedtext/extrahieren")
    assert r.status_code == 200, r.text
    assert "eleison" in r.json()["text"].lower()
    detail = (await client.get(f"/api/werke/{werk['id']}")).json()
    assert detail["projektionstext"] is None  # noch nicht gespeichert
    # speichern -> in GET /werke sichtbar
    saved = await client.put(f"/api/werke/{werk['id']}/liedtext", json={"text": "Kyrie eleison"})
    assert saved.status_code == 200
    detail = (await client.get(f"/api/werke/{werk['id']}")).json()
    assert detail["projektionstext"] == "Kyrie eleison"


MXML_AKKORD = (
    b'<?xml version="1.0"?>'
    b'<score-partwise version="3.1"><part-list>'
    b'<score-part id="P1"><part-name>V</part-name></score-part></part-list>'
    b'<part id="P1"><measure number="1">'
    b"<attributes><divisions>1</divisions><key><fifths>0</fifths></key></attributes>"
    b"<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration>"
    b"<lyric><syllabic>single</syllabic><text>Kyrie</text></lyric></note>"
    b"<note><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration></note>"
    b"<note><chord/><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration></note>"
    b"</measure></part></score-partwise>"
)


async def test_chordpro_aus_noten_erzeugen(client, conn):
    await _login(client, conn, name="cpgen")
    werk = (await client.post("/api/werke", json={"titel": "Kyrie"})).json()
    ausgabe_id = werk["ausgaben"][0]["id"]
    up = await client.post(
        "/api/dateien",
        files={"file": ("k.musicxml", MXML_AKKORD, "application/xml")},
        data={"ausgabe_id": str(ausgabe_id), "art": "scan_pdf"},
    )
    assert up.status_code == 200, up.text
    assert up.json()["art"] == "musicxml"
    r = await client.post(f"/api/werke/{werk['id']}/chordpro/erzeugen")
    assert r.status_code == 200, r.text
    txt = r.json()["text"]
    assert "[C]" in txt  # C-E-G -> C-Dur
    assert "Kyrie" in txt
    assert "{title:" in txt


async def test_upload_requires_role(client, conn):
    await _login(client, conn, name="gastuser", rolle="gast")
    ausgabe = await _make_ausgabe(conn)
    r = await client.post(
        "/api/dateien",
        files={"file": ("x.pdf", _pdf_bytes(1), "application/pdf")},
        data={"ausgabe_id": str(ausgabe)},
    )
    assert r.status_code == 403


async def test_upload_requires_auth(client, conn):
    ausgabe = await _make_ausgabe(conn)
    r = await client.post(
        "/api/dateien",
        files={"file": ("x.pdf", _pdf_bytes(1), "application/pdf")},
        data={"ausgabe_id": str(ausgabe)},
    )
    assert r.status_code == 401
