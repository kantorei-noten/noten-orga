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


async def _ausgabe(client):
    werk = (await client.post("/api/werke", json={"titel": "Annotationswerk"})).json()
    return werk["ausgaben"][0]["id"]


async def test_annotation_upsert_and_list(client, conn):
    await _login(client, conn, "anno1")
    ausgabe = await _ausgabe(client)
    body = {"ebene": "fingersatz", "seite": 1, "daten": {"paths": [[1, 2, 3]]}}
    r = await client.put(f"/api/ausgaben/{ausgabe}/annotationen", json=body)
    assert r.status_code == 200
    assert r.json()["ebene"] == "fingersatz"

    r = await client.get(f"/api/ausgaben/{ausgabe}/annotationen", params={"seite": 1})
    data = r.json()
    assert len(data) == 1
    assert data[0]["daten"] == {"paths": [[1, 2, 3]]}

    # Update ersetzt daten (kein Duplikat)
    body["daten"] = {"paths": [[9, 9]]}
    await client.put(f"/api/ausgaben/{ausgabe}/annotationen", json=body)
    data = (await client.get(f"/api/ausgaben/{ausgabe}/annotationen", params={"seite": 1})).json()
    assert len(data) == 1
    assert data[0]["daten"] == {"paths": [[9, 9]]}


async def test_annotation_delete(client, conn):
    await _login(client, conn, "anno2")
    ausgabe = await _ausgabe(client)
    r = await client.put(
        f"/api/ausgaben/{ausgabe}/annotationen",
        json={"ebene": "notiz", "seite": 2, "daten": {}},
    )
    ann_id = r.json()["id"]
    assert (await client.delete(f"/api/ausgaben/{ausgabe}/annotationen/{ann_id}")).status_code == 204
    data = (await client.get(f"/api/ausgaben/{ausgabe}/annotationen", params={"seite": 2})).json()
    assert data == []


async def test_annotation_acl_isolated_per_user(client, conn):
    # Nutzer A legt Annotation an
    await _login(client, conn, "annoA")
    ausgabe = await _ausgabe(client)
    await client.put(
        f"/api/ausgaben/{ausgabe}/annotationen",
        json={"ebene": "registrierung", "seite": 1, "daten": {"x": 1}},
    )
    # Nutzer B sieht sie nicht (Objekt-ACL)
    await _login(client, conn, "annoB")
    data = (await client.get(f"/api/ausgaben/{ausgabe}/annotationen", params={"seite": 1})).json()
    assert data == []


async def test_annotation_requires_role(client, conn):
    await _login(client, conn, "annogast", rolle="gast")
    ausgabe_dummy = "00000000-0000-0000-0000-000000000000"
    r = await client.put(
        f"/api/ausgaben/{ausgabe_dummy}/annotationen",
        json={"ebene": "notiz", "seite": 1, "daten": {}},
    )
    assert r.status_code == 403
