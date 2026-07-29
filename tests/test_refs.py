import pyotp

from app.auth import service as auth_service


async def _login(client, conn, name, rolle="musiker"):
    await conn.execute("delete from benutzer where benutzername = %s", (name,))
    u = await auth_service.create_user(conn, name, "Geheim1234!", rolle)
    code = pyotp.TOTP(u["totp_secret"]).now()
    r = await client.post(
        "/api/auth/login", json={"username": name, "password": "Geheim1234!", "totp": code}
    )
    assert r.status_code == 200
    return u


async def test_besetzung_crud(client, conn):
    await _login(client, conn, "ref_mus")
    r = await client.post("/api/besetzungen", json={"kuerzel": "TSTB", "name": "Testchor", "sortierung": 9})
    assert r.status_code == 201, r.text
    liste = (await client.get("/api/besetzungen")).json()
    assert any(b["kuerzel"] == "TSTB" and "sortierung" in b for b in liste)
    # umbenennen
    r = await client.patch("/api/besetzungen/TSTB", json={"name": "Neuer Name"})
    assert r.status_code == 200 and r.json()["name"] == "Neuer Name"
    # Duplikat -> 409
    r = await client.post("/api/besetzungen", json={"kuerzel": "TSTB", "name": "x"})
    assert r.status_code == 409
    # löschen (unbenutzt) -> 204
    assert (await client.delete("/api/besetzungen/TSTB")).status_code == 204


async def test_sammlung_art_in_verwendung(client, conn):
    await _login(client, conn, "ref_mus2")
    assert (await client.post("/api/sammlung-arten", json={"kuerzel": "testart", "name": "Testart"})).status_code == 201
    # unbekannte Art -> 400
    assert (await client.post("/api/sammlungen", json={"name": "X", "art": "gibtsnicht"})).status_code == 400
    # gültige neue Art verwenden
    s = await client.post("/api/sammlungen", json={"name": "Meine", "art": "testart"})
    assert s.status_code == 201
    # Art in Verwendung -> 409
    assert (await client.delete("/api/sammlung-arten/testart")).status_code == 409
    # Sammlung weg -> Art löschbar
    await client.delete(f"/api/sammlungen/{s.json()['id']}")
    assert (await client.delete("/api/sammlung-arten/testart")).status_code == 204


async def test_sammlung_art_name_und_bearbeiten(client, conn):
    await _login(client, conn, "ref_mus4")
    await client.post("/api/sammlung-arten", json={"kuerzel": "adv", "name": "Adventszeit"})
    sid = (await client.post("/api/sammlungen", json={"name": "S", "art": "adv"})).json()["id"]
    # Liste liefert Klartext-Namen
    row = next(x for x in (await client.get("/api/sammlungen")).json() if x["id"] == sid)
    assert row["art_name"] == "Adventszeit"
    # umbenennen + Art wechseln
    r = await client.patch(f"/api/sammlungen/{sid}", json={"name": "Neu", "art": "allgemein"})
    assert r.status_code == 200 and r.json()["name"] == "Neu" and r.json()["art_name"] == "Allgemein"
    # löschen
    assert (await client.delete(f"/api/sammlungen/{sid}")).status_code == 204


async def test_anlass_crud(client, conn):
    await _login(client, conn, "ref_mus3")
    r = await client.post("/api/anlaesse", json={"name": "Testfest", "sortierung": 9})
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    r = await client.patch(f"/api/anlaesse/{aid}", json={"name": "Fest 2", "sortierung": 3})
    assert r.status_code == 200 and r.json()["name"] == "Fest 2"
    assert (await client.delete(f"/api/anlaesse/{aid}")).status_code == 204


async def test_refs_pflege_erfordert_musiker(client, conn):
    await _login(client, conn, "ref_gast", rolle="gast")
    assert (await client.post("/api/besetzungen", json={"kuerzel": "X", "name": "y"})).status_code == 403
    assert (await client.post("/api/sammlung-arten", json={"kuerzel": "X", "name": "y"})).status_code == 403
    assert (await client.post("/api/anlaesse", json={"name": "y"})).status_code == 403
