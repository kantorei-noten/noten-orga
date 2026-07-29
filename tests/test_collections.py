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


async def _werk(client, titel):
    return (await client.post("/api/werke", json={"titel": titel})).json()["id"]


async def test_sammlung_flow(client, conn):
    await _login(client, conn, "coll1")
    s = (await client.post("/api/sammlungen", json={"name": "Orgel-Repertoire", "art": "orgel"})).json()
    sid = s["id"]
    assert s["art"] == "orgel"
    assert any(x["id"] == sid for x in (await client.get("/api/sammlungen")).json())

    w = await _werk(client, "Toccata")
    assert (await client.post(f"/api/sammlungen/{sid}/werke", json={"werk_id": w})).status_code == 204
    d = (await client.get(f"/api/sammlungen/{sid}")).json()
    assert any(x["id"] == w for x in d["werke"])

    lst = (await client.get("/api/sammlungen")).json()
    assert next(x for x in lst if x["id"] == sid)["anzahl_werke"] == 1

    assert (await client.delete(f"/api/sammlungen/{sid}/werke/{w}")).status_code == 204
    assert (await client.get(f"/api/sammlungen/{sid}")).json()["werke"] == []

    r = await client.patch(f"/api/sammlungen/{sid}", json={"name": "Orgel neu"})
    assert r.json()["name"] == "Orgel neu"
    assert (await client.delete(f"/api/sammlungen/{sid}")).status_code == 204
    assert (await client.get(f"/api/sammlungen/{sid}")).status_code == 404


async def test_sammlung_requires_role(client, conn):
    await _login(client, conn, "collgast", rolle="gast")
    assert (await client.post("/api/sammlungen", json={"name": "X"})).status_code == 403
