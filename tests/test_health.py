async def test_health_ok(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    # Minimiert: KEINE PG-Version / Fehlerdetails nach außen (kein Fingerprinting)
    assert "pg" not in body and "error" not in body
