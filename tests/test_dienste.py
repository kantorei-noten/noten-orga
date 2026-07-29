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
    return u["id"]


async def test_gruppe_dienst_flow(client, conn):
    await _login(client, conn, "chorleiter")
    # zweites Mitglied direkt in der DB anlegen
    saenger = await auth_service.create_user(conn, "saenger_x", "Geheim1234!", "chor")

    g = (await client.post("/api/gruppen", json={"name": "Kantorei", "art": "chor"})).json()
    gid = g["id"]
    assert g["art"] == "chor"

    # Mitglied zuordnen -> ganze Gruppe hat 1 Mitglied
    assert (
        await client.post(f"/api/gruppen/{gid}/mitglieder", json={"benutzer_id": str(saenger["id"])})
    ).status_code == 204
    gl = next(x for x in (await client.get("/api/gruppen")).json() if x["id"] == gid)
    assert gl["anzahl_mitglieder"] == 1

    # Setliste für den Dienst
    sid = (await client.post("/api/setlisten", json={"name": "1. Advent"})).json()["id"]

    # Gruppe als EIN Dienst planen
    d = (
        await client.post(
            "/api/dienste",
            json={"gruppe_id": gid, "setliste_id": sid, "datum": "2026-11-29", "notiz": "Kantate"},
        )
    ).json()
    assert d["bestaetigt"] is False

    liste = (await client.get("/api/dienste")).json()
    row = next(x for x in liste if x["id"] == d["id"])
    assert row["gruppe_name"] == "Kantorei"
    assert row["anzahl_mitglieder"] == 1
    assert row["setliste_name"] == "1. Advent"

    # bestätigen
    r = await client.patch(f"/api/dienste/{d['id']}", json={"bestaetigt": True})
    assert r.json()["bestaetigt"] is True


async def test_mitglieder_auswahl_und_loeschen(client, conn):
    await _login(client, conn, "chorleiter2")
    saenger = await auth_service.create_user(conn, "saenger_y", "Geheim1234!", "chor")
    # /benutzer/auswahl liefert Namen (musiker darf)
    namen = (await client.get("/api/benutzer/auswahl")).json()
    assert any(u["benutzername"] == "saenger_y" for u in namen)
    # Gruppe + Mitglied → list_gruppen liefert die Mitgliedernamen
    gid = (await client.post("/api/gruppen", json={"name": "Bläser", "art": "blaeser"})).json()["id"]
    await client.post(f"/api/gruppen/{gid}/mitglieder", json={"benutzer_id": str(saenger["id"])})
    g = next(x for x in (await client.get("/api/gruppen")).json() if x["id"] == gid)
    assert [m["benutzername"] for m in g["mitglieder"]] == ["saenger_y"]
    # Dienst anlegen + löschen, dann Gruppe löschen
    did = (await client.post("/api/dienste", json={"gruppe_id": gid})).json()["id"]
    assert (await client.delete(f"/api/dienste/{did}")).status_code == 204
    assert (await client.delete(f"/api/gruppen/{gid}")).status_code == 204


async def test_benutzer_auswahl_erfordert_musiker(client, conn):
    await _login(client, conn, "auswahlgast", rolle="gast")
    assert (await client.get("/api/benutzer/auswahl")).status_code == 403


async def test_zusage_flow(client, conn):
    await _login(client, conn, "chorleiter3")
    saenger = await auth_service.create_user(conn, "saenger_z", "Geheim1234!", "chor")
    gid = (await client.post("/api/gruppen", json={"name": "Kantorei2", "art": "chor"})).json()["id"]
    await client.post(f"/api/gruppen/{gid}/mitglieder", json={"benutzer_id": str(saenger["id"])})
    did = (await client.post("/api/dienste", json={"gruppe_id": gid, "datum": "2026-12-24"})).json()["id"]

    # als Sänger (Rolle chor) einloggen
    code = pyotp.TOTP(saenger["totp_secret"]).now()
    assert (await client.post("/api/auth/login", json={"username": "saenger_z", "password": "Geheim1234!", "totp": code})).status_code == 200
    # sieht seinen Dienst als offen
    m = (await client.get("/api/meine-dienste")).json()
    assert next(x for x in m if x["id"] == did)["mein_status"] == "offen"
    # zusagen mit Notiz
    r = await client.post(f"/api/dienste/{did}/zusage", json={"status": "zugesagt", "notiz": "ab 9:30"})
    assert r.status_code == 200 and r.json()["status"] == "zugesagt"
    assert next(x for x in (await client.get("/api/meine-dienste")).json() if x["id"] == did)["mein_status"] == "zugesagt"
    # in der Teilnehmerliste sichtbar (chor darf GET /dienste)
    d = next(x for x in (await client.get("/api/dienste")).json() if x["id"] == did)
    t = next(x for x in d["teilnehmer"] if x["benutzername"] == "saenger_z")
    assert t["status"] == "zugesagt" and t["notiz"] == "ab 9:30"


async def test_dienst_editierbar_und_fremde_zusage(client, conn):
    await _login(client, conn, "chorleiter4")
    gid = (await client.post("/api/gruppen", json={"name": "KG", "art": "chor"})).json()["id"]
    did = (await client.post("/api/dienste", json={"gruppe_id": gid})).json()["id"]
    # Termin nachträglich editieren
    r = await client.patch(f"/api/dienste/{did}", json={"datum": "2026-12-25", "notiz": "Christmette"})
    assert r.status_code == 200 and r.json()["notiz"] == "Christmette" and str(r.json()["datum"]) == "2026-12-25"
    # Nicht-Eingetragener kann nicht zusagen
    await _login(client, conn, "fremder", rolle="chor")
    assert (await client.post(f"/api/dienste/{did}/zusage", json={"status": "zugesagt"})).status_code == 403


async def test_gruppe_requires_role(client, conn):
    await _login(client, conn, "dienstgast", rolle="gast")
    assert (await client.post("/api/gruppen", json={"name": "X"})).status_code == 403
