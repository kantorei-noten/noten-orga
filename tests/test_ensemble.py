import pymupdf
import pyotp

from app.auth import service as auth_service


def _pdf(pages=2):
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"S{i + 1}")
    return doc.tobytes()


async def _login(client, conn, name, rolle="musiker"):
    await conn.execute("delete from benutzer where benutzername = %s", (name,))
    u = await auth_service.create_user(conn, name, "Geheim1234!", rolle)
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login", json={"username": name, "password": "Geheim1234!", "totp": code}
    )
    assert r.status_code == 200


async def _ausgabe_mit_datei(client, conn):
    werk = (await client.post("/api/werke", json={"titel": "Chorwerk"})).json()
    ausgabe = werk["ausgaben"][0]["id"]
    up = await client.post(
        "/api/dateien",
        files={"file": ("s.pdf", _pdf(4), "application/pdf")},
        data={"ausgabe_id": ausgabe, "art": "scan_pdf"},
    )
    return ausgabe, up.json()["id"]


async def test_geteilte_annotationsebene(client, conn):
    # Chorleiter A legt geteilte Ebene an
    await _login(client, conn, "leiterA")
    werk = (await client.post("/api/werke", json={"titel": "Ensemble"})).json()
    ausgabe = werk["ausgaben"][0]["id"]
    await client.put(
        f"/api/ausgaben/{ausgabe}/annotationen",
        json={"ebene": "einsaetze", "seite": 1, "daten": {"x": 1}, "geteilt": True},
    )
    await client.put(
        f"/api/ausgaben/{ausgabe}/annotationen",
        json={"ebene": "privat", "seite": 1, "daten": {"y": 2}, "geteilt": False},
    )
    # Sänger B: sieht die geteilte Ebene, nicht die private
    await _login(client, conn, "saengerB")
    geteilt = (await client.get(f"/api/ausgaben/{ausgabe}/annotationen/geteilt?seite=1")).json()
    ebenen = [g["ebene"] for g in geteilt]
    assert "einsaetze" in ebenen
    assert "privat" not in ebenen
    # eigene (leere) Ansicht von B
    eigen = (await client.get(f"/api/ausgaben/{ausgabe}/annotationen?seite=1")).json()
    assert eigen == []


async def test_stimmen_liste(client, conn):
    await _login(client, conn, "leiter2")
    ausgabe, datei_id = await _ausgabe_mit_datei(client, conn)
    await conn.execute(
        "insert into stimme (datei_id, name, seite_von, seite_bis, sortierung) values (%s,'Sopran',1,1,1)",
        (datei_id,),
    )
    await conn.execute(
        "insert into stimme (datei_id, name, seite_von, seite_bis, sortierung) values (%s,'Bass',2,2,2)",
        (datei_id,),
    )
    liste = (await client.get(f"/api/ausgaben/{ausgabe}/stimmen-liste")).json()
    namen = [s["name"] for s in liste]
    assert namen == ["Sopran", "Bass"]
    # PDF je Stimme abrufbar (Copyright public_domain setzen)
    await conn.execute("update ausgabe set rechtestatus='public_domain' where id=%s", (ausgabe,))
    r = await client.get(f"/api/druck/stimme/{liste[0]['id']}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
