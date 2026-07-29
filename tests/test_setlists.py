import pymupdf
import pyotp

from app.auth import service as auth_service


def _pdf(pages: int = 3) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"S{i + 1}")
    return doc.tobytes()


async def _login(client, conn, name="setl", rolle="musiker"):
    await conn.execute("delete from benutzer where benutzername = %s", (name,))
    u = await auth_service.create_user(conn, name, "Geheim1234!", rolle)
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login",
        json={"username": name, "password": "Geheim1234!", "totp": code},
    )
    assert r.status_code == 200


async def test_setliste_full_flow(client, conn):
    await _login(client, conn)
    werk = (await client.post("/api/werke", json={"titel": "Präludium"})).json()
    ausgabe_id = werk["ausgaben"][0]["id"]
    up = await client.post(
        "/api/dateien",
        files={"file": ("s.pdf", _pdf(3), "application/pdf")},
        data={"ausgabe_id": ausgabe_id, "art": "scan_pdf"},
    )
    assert up.status_code == 200

    sid = (await client.post("/api/setlisten", json={"name": "Gottesdienst 1. Advent"})).json()["id"]

    # ganzes Werk -> Auflösung auf bevorzugte Ausgabe + Datei
    e1 = (
        await client.post(f"/api/setlisten/{sid}/eintraege", json={"typ": "werk", "werk_id": werk["id"]})
    ).json()
    assert e1["werk_titel"] == "Präludium"
    assert e1["aufgeloeste_ausgabe_id"] == ausgabe_id
    assert e1["datei_id"] is not None
    assert e1["seiten"] == 3

    # Abschnitt (Bookmark: 2. Strophe)
    e2 = (
        await client.post(
            f"/api/setlisten/{sid}/eintraege",
            json={"typ": "abschnitt", "titel": "2. Strophe", "seite_von": 2, "seite_bis": 2},
        )
    ).json()

    detail = (await client.get(f"/api/setlisten/{sid}")).json()
    assert [e["id"] for e in detail["eintraege"]] == [e1["id"], e2["id"]]

    # Reihenfolge tauschen
    d2 = (
        await client.put(
            f"/api/setlisten/{sid}/reihenfolge", json={"eintrag_ids": [e2["id"], e1["id"]]}
        )
    ).json()
    assert [e["id"] for e in d2["eintraege"]] == [e2["id"], e1["id"]]

    # Eintrag löschen
    assert (
        await client.delete(f"/api/setlisten/{sid}/eintraege/{e1['id']}")
    ).status_code == 204
    assert len((await client.get(f"/api/setlisten/{sid}")).json()["eintraege"]) == 1

    # Liste + Setliste löschen
    assert any(x["id"] == sid for x in (await client.get("/api/setlisten")).json())
    assert (await client.delete(f"/api/setlisten/{sid}")).status_code == 204
    assert (await client.get(f"/api/setlisten/{sid}")).status_code == 404


async def test_setliste_update(client, conn):
    await _login(client, conn)
    s = (await client.post("/api/setlisten", json={"name": "Alt"})).json()
    r = await client.patch(f"/api/setlisten/{s['id']}", json={"name": "Neu", "notiz": "Hinweis"})
    assert r.json()["name"] == "Neu"
    assert r.json()["notiz"] == "Hinweis"


async def test_eintrag_bearbeiten(client, conn):
    await _login(client, conn, name="setl2")
    werk = (await client.post("/api/werke", json={"titel": "Motette"})).json()
    ausgabe_id = werk["ausgaben"][0]["id"]
    up = await client.post(
        "/api/dateien",
        files={"file": ("m.pdf", _pdf(6), "application/pdf")},
        data={"ausgabe_id": ausgabe_id, "art": "scan_pdf"},
    )
    datei_id = up.json()["id"]
    sid = (await client.post("/api/setlisten", json={"name": "GD"})).json()["id"]

    # ganzes Werk (nicht gepinnt)
    e = (
        await client.post(f"/api/setlisten/{sid}/eintraege", json={"typ": "werk", "werk_id": werk["id"]})
    ).json()
    assert e["gepinnt_datei_id"] is None
    assert e["seite_von"] is None

    # nachträglich: Seitenbereich 3–6 setzen
    e2 = (
        await client.patch(
            f"/api/setlisten/{sid}/eintraege/{e['id']}",
            json={"datei_id": datei_id, "seite_von": 3, "seite_bis": 6},
        )
    ).json()
    assert e2["gepinnt_datei_id"] == datei_id
    assert e2["seite_von"] == 3 and e2["seite_bis"] == 6

    # nachträglich: wieder alles (Seiten leeren)
    e3 = (
        await client.patch(
            f"/api/setlisten/{sid}/eintraege/{e['id']}",
            json={"seite_von": None, "seite_bis": None},
        )
    ).json()
    assert e3["seite_von"] is None and e3["seite_bis"] is None
    assert e3["gepinnt_datei_id"] == datei_id  # Blatt bleibt gepinnt

    # unbekannter Eintrag -> 404
    fake = "00000000-0000-0000-0000-000000000000"
    assert (
        await client.patch(f"/api/setlisten/{sid}/eintraege/{fake}", json={"seite_von": 1})
    ).status_code == 404


async def test_abschnitt_umbenennen(client, conn):
    await _login(client, conn, name="setl3")
    sid = (await client.post("/api/setlisten", json={"name": "GD2"})).json()["id"]
    e = (await client.post(f"/api/setlisten/{sid}/eintraege", json={"typ": "abschnitt", "titel": "Eingang"})).json()
    r = await client.patch(f"/api/setlisten/{sid}/eintraege/{e['id']}", json={"titel": "Ausgang"})
    assert r.status_code == 200 and r.json()["titel"] == "Ausgang"
    detail = (await client.get(f"/api/setlisten/{sid}")).json()
    assert detail["eintraege"][0]["titel"] == "Ausgang"


async def test_setliste_requires_role(client, conn):
    await _login(client, conn, name="gast3", rolle="gast")
    assert (await client.post("/api/setlisten", json={"name": "X"})).status_code == 403
