"""La base de la console. Aucun appel réseau, aucune clé d'API."""

import json

import pytest

from agent_growth import store


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def brand_id(conn):
    return store.add_brand(conn, slug="egyptours", name="Egyptours", url="https://egyptours.fr")


def test_catalog_is_seeded_on_connect(conn):
    """Le catalogue est de la donnée de référence : il existe dès l'ouverture."""
    tools = store.list_integrations(conn)
    assert len(tools) == len(store.CATALOG)
    assert {t["state"] for t in tools} == {"disponible"}


def test_recording_a_measure_twice_overwrites_it(conn, brand_id):
    """Rejouer une collecte ne duplique rien — c'est ce qui permet de la relancer."""
    store.record(conn, [(brand_id, "instagram", "abonnes", "2026-10-10", 1200)])
    store.record(conn, [(brand_id, "instagram", "abonnes", "2026-10-10", 1250)])
    rows = store.series(conn, brand_id, "instagram", "abonnes")
    assert [(r["day"], r["value"]) for r in rows] == [("2026-10-10", 1250)]


def test_totals_compare_two_consecutive_windows(conn, brand_id):
    import datetime

    today = datetime.date.today()
    # 10 dans la fenêtre courante, 4 dans la précédente.
    store.record(conn, [(brand_id, "seo", "visites", (today - datetime.timedelta(days=3)).isoformat(), 10)])
    store.record(conn, [(brand_id, "seo", "visites", (today - datetime.timedelta(days=40)).isoformat(), 4)])
    row = store.totals(conn, brand_id, days=30)[0]
    assert row["current"] == 10
    assert row["previous"] == 4


def test_unknown_channel_is_refused(conn, brand_id):
    with pytest.raises(ValueError, match="Canal inconnu"):
        store.add_channel(conn, brand_id, "myspace")


def test_connect_integration_refuses_a_real_looking_secret(conn):
    """La base ne doit jamais contenir un secret, seulement sa référence."""
    with pytest.raises(ValueError, match="ressemble à un secret"):
        store.connect_integration(conn, "brevo", secret_ref="sk-live-9f2c")
    store.connect_integration(conn, "brevo", secret_ref="BREVO_API_KEY")
    row = next(r for r in store.list_integrations(conn) if r["slug"] == "brevo")
    assert row["state"] == "connecte"
    assert row["secret_ref"] == "BREVO_API_KEY"


def test_connect_integration_rejects_unknown_tool(conn):
    with pytest.raises(KeyError):
        store.connect_integration(conn, "outil-inexistant", secret_ref="X")


def test_prospect_requires_an_origin(conn, brand_id):
    """Sans origine tracée, on n'a pas le droit de contacter (RGPD)."""
    with pytest.raises(ValueError, match="origine"):
        store.add_prospect(conn, brand_id, company="Hotel X", source="  ")


def test_opt_out_applies_across_all_brands_and_cancels_pending_sends(conn, brand_id):
    other = store.add_brand(conn, slug="oria", name="Oria", url="https://oria.fr")
    for bid in (brand_id, other):
        pid = store.add_prospect(conn, bid, company="Hotel X", source="import",
                                 email="dg@hotelx.example")
        conn.execute(
            "INSERT INTO outreach (prospect_id, state, created_at) VALUES (?, 'prevu', ?)",
            (pid, store.now()),
        )
    conn.commit()

    assert store.opt_out(conn, "dg@hotelx.example") == 2
    states = {r["state"] for r in conn.execute("SELECT state FROM outreach")}
    assert states == {"annule"}
    assert store.pipeline(conn, brand_id) == {"exclu": 1}


def test_contactable_excludes_opted_out_and_unqualified(conn, brand_id):
    ok = store.add_prospect(conn, brand_id, company="Bon", source="import",
                            email="ok@x.example", icp_fit=80)
    conn.execute("UPDATE prospect SET state = 'qualifie' WHERE id = ?", (ok,))
    out = store.add_prospect(conn, brand_id, company="Exclu", source="import",
                             email="no@x.example", icp_fit=90)
    conn.execute("UPDATE prospect SET state = 'qualifie' WHERE id = ?", (out,))
    conn.commit()
    store.opt_out(conn, "no@x.example")

    emails = [r["email"] for r in store.contactable(conn, brand_id)]
    assert emails == ["ok@x.example"]


def test_prospect_without_email_does_not_collide(conn, brand_id):
    """L'index unique sur l'e-mail est partiel : deux contacts sans e-mail coexistent."""
    store.add_prospect(conn, brand_id, company="A", source="import")
    store.add_prospect(conn, brand_id, company="B", source="import")
    assert store.pipeline(conn, brand_id) == {"trouve": 2}


def test_import_brand_core_deduces_channels_from_the_angles(conn, tmp_path, doc):
    """Premier bénéfice concret du contrat brand-core : les canaux se déduisent."""
    path = tmp_path / "brand-core.json"
    path.write_text(json.dumps(doc.model_dump(), ensure_ascii=False), encoding="utf-8")

    bid = store.import_brand_core(conn, path)
    kinds = {c["kind"] for c in store.list_channels(conn, bid)}
    # L'angle du fixture cible les familles social, seo et gmb. « social » est
    # traduit en canal concret : on n'enregistre jamais une famille telle quelle.
    assert {"instagram", "seo", "gmb", "site", "geo"} <= kinds
    assert "social" not in kinds
    brand = store.get_brand(conn, "salonlea-fr")
    assert brand["name"] == "Salon Léa"
    # La marque mémorise où vit sa ligne éditoriale.
    assert brand["core_path"] == str(path)


def test_import_brand_core_is_idempotent(conn, tmp_path, doc):
    path = tmp_path / "brand-core.json"
    path.write_text(json.dumps(doc.model_dump(), ensure_ascii=False), encoding="utf-8")
    first = store.import_brand_core(conn, path)
    assert store.import_brand_core(conn, path) == first
    assert len(store.list_brands(conn)) == 1


def test_portfolio_reports_connected_channels_and_revenue(conn, brand_id):
    store.add_channel(conn, brand_id, "instagram")
    store.add_channel(conn, brand_id, "google_ads")
    conn.execute("UPDATE channel SET state = 'connecte' WHERE kind = 'instagram'")
    conn.commit()
    store.add_brand(conn, slug="oria", name="Oria", url="https://oria.fr",
                    kind="client", monthly_fee_eur=1490)

    rows = {r["brand"]["slug"]: r for r in store.portfolio(conn)}
    assert rows["egyptours"]["connected"] == 1
    assert len(rows["egyptours"]["channels"]) == 2
    assert store.revenue(conn) == {"mrr": 1490, "clients": 1}


def test_an_older_database_gains_the_new_columns(tmp_path):
    """Une base créée avant l'ajout d'une colonne doit continuer à s'ouvrir."""
    import sqlite3

    db = tmp_path / "ancienne.db"
    old = sqlite3.connect(db)
    old.execute(
        """CREATE TABLE brand (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE,
                               name TEXT NOT NULL, url TEXT NOT NULL,
                               kind TEXT NOT NULL DEFAULT 'interne',
                               status TEXT NOT NULL DEFAULT 'actif',
                               plan TEXT, monthly_fee_eur REAL,
                               notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)"""
    )
    old.execute("INSERT INTO brand (slug, name, url, created_at) VALUES ('x','X','https://x.fr','2026-01-01')")
    old.commit()
    old.close()

    conn = store.connect(db)
    brand = store.get_brand(conn, "x")
    assert brand["core_path"] == ""
    assert brand["name"] == "X"
    conn.close()


def _day(n: int) -> str:
    import datetime
    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()


def test_outcome_separates_result_from_activity(conn, brand_id):
    """Un client achète des acquisitions à un coût connu, pas des abonnés."""
    store.record(conn, [
        (brand_id, "google_ads", "leads", _day(3), 8),
        (brand_id, "google_ads", "cout_eur", _day(3), 400),
        (brand_id, "instagram", "abonnes", _day(2), 1500),
    ])
    o = store.outcome(conn, brand_id)
    assert o["measured"] is True
    assert o["acquired"] == 8
    assert o["cost"] == 400
    assert o["cpa"] == 50

    # Les abonnés ne polluent pas le résultat : ils sont du diagnostic.
    assert [(r["channel"], r["metric"]) for r in store.activity(conn, brand_id)] == [
        ("instagram", "abonnes")
    ]


def test_outcome_compares_with_the_previous_period(conn, brand_id):
    store.record(conn, [
        (brand_id, "google_ads", "leads", _day(3), 8),
        (brand_id, "google_ads", "cout_eur", _day(3), 400),
        (brand_id, "google_ads", "leads", _day(40), 4),
        (brand_id, "google_ads", "cout_eur", _day(40), 320),
    ])
    o = store.outcome(conn, brand_id)
    assert o["cpa"] == 50
    assert o["previous_cpa"] == 80   # le coût d'acquisition a baissé


def test_outcome_says_when_nothing_is_measured(conn, brand_id):
    """« On ne sait pas » ne doit jamais s'afficher comme « c'est gratuit »."""
    store.record(conn, [(brand_id, "instagram", "abonnes", _day(1), 900)])
    o = store.outcome(conn, brand_id)
    assert o["measured"] is False
    assert o["cpa"] is None
    assert o["roas"] is None


def test_roas_is_reported_when_revenue_is_attributed(conn, brand_id):
    store.record(conn, [
        (brand_id, "google_ads", "cout_eur", _day(2), 500),
        (brand_id, "google_ads", "ca_eur", _day(2), 2000),
        (brand_id, "google_ads", "ventes", _day(2), 10),
    ])
    assert store.outcome(conn, brand_id)["roas"] == 4.0
