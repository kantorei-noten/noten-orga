import io
import zipfile

import pyotp

from app.auth import service as auth_service

VALID_MUSICXML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<score-partwise version="3.1"><part-list>'
    b'<score-part id="P1"><part-name>Orgel</part-name></score-part></part-list>'
    b'<part id="P1"><measure number="1">'
    b"<note><pitch><step>C</step><octave>4</octave></pitch>"
    b"<duration>4</duration><type>whole</type></note></measure></part></score-partwise>"
)


def _mxl(xml: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container><rootfiles>'
            '<rootfile full-path="score.xml" media-type="application/vnd.recordare.musicxml+xml"/>'
            "</rootfiles></container>",
        )
        z.writestr("score.xml", xml)
    return buf.getvalue()


async def _login(client, conn, name="omr", rolle="musiker"):
    await conn.execute("delete from benutzer where benutzername = %s", (name,))
    u = await auth_service.create_user(conn, name, "Geheim1234!", rolle)
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login", json={"username": name, "password": "Geheim1234!", "totp": code}
    )
    assert r.status_code == 200


async def _werk_ausgabe(client):
    werk = (await client.post("/api/werke", json={"titel": "OMR-Werk"})).json()
    return werk["ausgaben"][0]["id"]


async def _upload(client, ausgabe_id, filename, data):
    r = await client.post(
        "/api/dateien",
        files={"file": (filename, data, "application/octet-stream")},
        data={"ausgabe_id": ausgabe_id, "art": "scan_pdf"},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def test_plain_musicxml_endpoint(client, conn):
    await _login(client, conn)
    ausgabe = await _werk_ausgabe(client)
    did = await _upload(client, ausgabe, "stueck.musicxml", VALID_MUSICXML)
    r = await client.get(f"/api/dateien/{did}/musicxml")
    assert r.status_code == 200
    assert "score-partwise" in r.text
    assert "musicxml" in r.headers["content-type"]


async def test_mxl_extraction(client, conn):
    await _login(client, conn)
    ausgabe = await _werk_ausgabe(client)
    did = await _upload(client, ausgabe, "stueck.mxl", _mxl(VALID_MUSICXML))
    r = await client.get(f"/api/dateien/{did}/musicxml")
    assert r.status_code == 200
    assert "score-partwise" in r.text


async def test_pdf_has_no_musicxml(client, conn):
    import pymupdf

    await _login(client, conn)
    ausgabe = await _werk_ausgabe(client)
    doc = pymupdf.open()
    doc.new_page()
    did = await _upload(client, ausgabe, "scan.pdf", doc.tobytes())
    r = await client.get(f"/api/dateien/{did}/musicxml")
    assert r.status_code == 415


async def test_omr_status_default(client, conn):
    await _login(client, conn)
    werk = (await client.post("/api/werke", json={"titel": "OMR-Status"})).json()
    assert werk["ausgaben"][0]["omr_status"] == "kein"
