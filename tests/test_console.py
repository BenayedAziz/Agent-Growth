"""Les écrans de la console, servis par un vrai client HTTP de test.

Ces tests existent pour une raison précise : un appel à `TemplateResponse` avec
la mauvaise signature rend un gabarit valide mais renvoie une 500. Seul un test
qui passe par la couche HTTP l'attrape.
"""

import html
import json

import pytest
from fastapi.testclient import TestClient

from agent_growth import store
from agent_growth.console.app import create_app


@pytest.fixture
def client(tmp_path, doc):
    db = tmp_path / "console.db"
    conn = store.connect(db)

    core = tmp_path / "brand-core.json"
    core.write_text(json.dumps(doc.model_dump(), ensure_ascii=False), encoding="utf-8")
    bid = store.import_brand_core(conn, core)
    conn.execute("UPDATE brand SET kind = 'client', monthly_fee_eur = 1490 WHERE id = ?", (bid,))
    conn.commit()
    store.record(conn, [(bid, "seo", "visites", "2026-10-13", 120)])
    store.add_prospect(conn, bid, company="Hotel X", source="google_places", email="a@x.example")
    store.connect_integration(conn, "ga4", secret_ref="GOOGLE_OAUTH_REFRESH")
    conn.close()

    return TestClient(create_app(db))


def text(response) -> str:
    """Le HTML rendu, apostrophes et accents dés-échappés, pour pouvoir y
    chercher les phrases telles qu'elles sont écrites dans les gabarits."""
    return html.unescape(response.text)


def test_portfolio_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Portefeuille" in text(r)
    assert "Salon Léa" in text(r)
    assert "1490" in text(r)  # revenu mensuel


def test_portfolio_warns_about_unconnected_channels(client):
    assert "pas encore connect" in text(client.get("/"))


def test_brand_page_shows_the_editorial_line(client):
    r = client.get("/marque/salonlea-fr")
    assert r.status_code == 200
    assert "Ligne éditoriale" in text(r)
    assert "Vos boucles, coupées à sec" in text(r)
    assert "dompter" in text(r)          # vocabulaire banni
    assert "Avant / après" in text(r)    # pilier


def test_brand_page_shows_measures_and_pipeline(client):
    r = client.get("/marque/salonlea-fr")
    assert "visites" in text(r)
    assert "Prospection" in text(r)
    assert "Trouvés" in text(r)


def test_unknown_brand_is_a_404_not_a_crash(client):
    r = client.get("/marque/inexistant")
    assert r.status_code == 404
    assert "introuvable" in text(r)


def test_tools_page_lists_the_catalog_with_access_gates(client):
    r = client.get("/outils")
    assert r.status_code == 200
    assert "Google Analytics 4" in text(r)
    assert "Revue d'app requise" in text(r)     # Meta
    assert "Demande d'accès" in text(r)         # fiche Google
    assert "GOOGLE_OAUTH_REFRESH" in text(r)    # la référence, pas le secret


def test_tools_page_never_shows_a_secret_value(client):
    """Garde-fou : la page des outils n'affiche que des références."""
    assert "sk-" not in text(client.get("/outils"))
