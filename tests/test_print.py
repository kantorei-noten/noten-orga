import uuid

import pymupdf
import pyotp

from app.auth import service as auth_service


def _pdf(pages: int) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Seite {i + 1}")
    return doc.tobytes()


async def _login(client, conn, name="druck", rolle="musiker"):
    await conn.execute("delete from benutzer where benutzername = %s", (name,))
    u = await auth_service.create_user(conn, name, "Geheim1234!", rolle)
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login", json={"username": name, "password": "Geheim1234!", "totp": code}
    )
    assert r.status_code == 200


async def _setup(client, conn, pages=3, rechte="unbekannt"):
    werk = (await client.post("/api/werke", json={"titel": "Druckwerk"})).json()
    ausgabe_id = werk["ausgaben"][0]["id"]
    up = await client.post(
        "/api/dateien",
        files={"file": ("s.pdf", _pdf(pages), "application/pdf")},
        data={"ausgabe_id": ausgabe_id, "art": "scan_pdf"},
    )
    assert up.status_code == 200
    datei_id = up.json()["id"]
    await conn.execute("update ausgabe set rechtestatus = %s where id = %s", (rechte, ausgabe_id))
    return werk, ausgabe_id, datei_id


async def test_setlist_pdf_blocked_when_unknown(client, conn):
    await _login(client, conn)
    werk, _, _ = await _setup(client, conn, rechte="unbekannt")
    sid = (await client.post("/api/setlisten", json={"name": "GD"})).json()["id"]
    await client.post(f"/api/setlisten/{sid}/eintraege", json={"typ": "werk", "werk_id": werk["id"]})
    r = await client.get(f"/api/druck/setliste/{sid}")
    assert r.status_code == 403  # Copyright-Gate fail-closed


async def test_setlist_pdf_ok_public_domain(client, conn):
    await _login(client, conn)
    werk, _, _ = await _setup(client, conn, pages=3, rechte="public_domain")
    sid = (await client.post("/api/setlisten", json={"name": "GD2"})).json()["id"]
    await client.post(f"/api/setlisten/{sid}/eintraege", json={"typ": "werk", "werk_id": werk["id"]})
    r = await client.get(f"/api/druck/setliste/{sid}")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    doc = pymupdf.open(stream=r.content, filetype="pdf")
    assert doc.page_count == 3
    assert any("Druckwerk" in t[1] for t in doc.get_toc())  # Bookmark gesetzt


async def test_setlist_pdf_a4_normalisierung(client, conn):
    await _login(client, conn)
    werk, _, _ = await _setup(client, conn, pages=2, rechte="public_domain")
    sid = (await client.post("/api/setlisten", json={"name": "GD-A4"})).json()["id"]
    await client.post(f"/api/setlisten/{sid}/eintraege", json={"typ": "werk", "werk_id": werk["id"]})
    r = await client.get(f"/api/druck/setliste/{sid}?a4=true&bundsteg_mm=15")
    assert r.status_code == 200
    doc = pymupdf.open(stream=r.content, filetype="pdf")
    rect = doc[0].rect
    assert abs(rect.width - 595) < 2 and abs(rect.height - 842) < 2  # A4
    assert any("Druckwerk" in t[1] for t in doc.get_toc())  # Bookmarks erhalten


async def test_einzelstimme(client, conn):
    await _login(client, conn)
    _, _, datei_id = await _setup(client, conn, pages=4, rechte="public_domain")
    cur = await conn.execute(
        "insert into stimme (datei_id, name, seite_von, seite_bis) values (%s,'Sopran',1,2) returning id",
        (datei_id,),
    )
    stimme_id = (await cur.fetchone())["id"]
    r = await client.get(f"/api/druck/stimme/{stimme_id}")
    assert r.status_code == 200
    doc = pymupdf.open(stream=r.content, filetype="pdf")
    assert doc.page_count == 2


async def test_stimmen_batch(client, conn):
    await _login(client, conn)
    _, ausgabe_id, datei_id = await _setup(client, conn, pages=4, rechte="public_domain")
    await conn.execute(
        "insert into stimme (datei_id, name, seite_von, seite_bis, sortierung) values (%s,'Sopran',1,1,1)",
        (datei_id,),
    )
    await conn.execute(
        "insert into stimme (datei_id, name, seite_von, seite_bis, sortierung) values (%s,'Alt',2,2,2)",
        (datei_id,),
    )
    r = await client.get(f"/api/druck/ausgabe/{ausgabe_id}/stimmen")
    assert r.status_code == 200
    doc = pymupdf.open(stream=r.content, filetype="pdf")
    assert doc.page_count == 2
    names = [t[1] for t in doc.get_toc()]
    assert "Sopran" in names and "Alt" in names


async def test_druck_requires_role(client, conn):
    await _login(client, conn, name="gast4", rolle="gast")
    r = await client.get(f"/api/druck/setliste/{uuid.uuid4()}")
    assert r.status_code == 403
