async def test_core_tables(conn):
    cur = await conn.execute(
        "select table_name from information_schema.tables where table_schema='public'"
    )
    names = {r["table_name"] for r in await cur.fetchall()}
    for t in [
        "werk", "fassung", "ausgabe", "datei", "stimme",
        "gesangbuch", "gesangbuch_eintrag", "anlass", "tag",
        "werk_anlass", "werk_tag", "setliste", "setliste_eintrag", "besetzung",
    ]:
        assert t in names, f"Tabelle fehlt: {t}"


async def test_seed_vokabulare(conn):
    cur = await conn.execute("select count(*) as n from gesangbuch")
    assert (await cur.fetchone())["n"] >= 2
    cur = await conn.execute("select count(*) as n from anlass")
    assert (await cur.fetchone())["n"] >= 10
    cur = await conn.execute("select count(*) as n from besetzung")
    assert (await cur.fetchone())["n"] >= 5


async def test_deutsche_akzentunempfindliche_suche(conn):
    # ö -> o: 'Töne' muss auf 'tone' matchen
    cur = await conn.execute(
        "select to_tsvector('deutsch_unaccent','Töne der Orgel') "
        "@@ plainto_tsquery('deutsch_unaccent','tone') as m"
    )
    assert (await cur.fetchone())["m"] is True


async def test_werk_such_tsv_trigger(conn):
    await conn.execute(
        "insert into werk (titel, komponist) values ('Nun danket alle Gott','Johann Crüger')"
    )
    try:
        cur = await conn.execute(
            "select count(*) as n from werk "
            "where such_tsv @@ plainto_tsquery('deutsch_unaccent','cruger danket')"
        )
        assert (await cur.fetchone())["n"] >= 1
    finally:
        await conn.execute("delete from werk where titel='Nun danket alle Gott'")
