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


def test_portfolio_leads_with_the_result_not_the_activity(client):
    """Premiers principes : le résultat passe avant l'activité, à l'écran aussi."""
    body = text(client.get("/"))
    assert "Résultat du portefeuille" in body
    # L'écran doit dire franchement qu'il n'y a pas de résultat mesuré,
    # au lieu de remplir la place avec des visites.
    assert "Aucun résultat mesuré" in body
    assert body.index("Résultat du portefeuille") < body.index("marques pilotées")


def test_brand_page_shows_result_before_activity(client):
    body = text(client.get("/marque/salonlea-fr"))
    assert body.index("Résultat") < body.index("Activité")
    assert "pour dire si ça marche" in body  # l'avertissement sur l'activité


def test_measured_outcome_is_displayed_with_its_cost_per_acquisition(tmp_path, doc):
    import datetime
    import json as _json

    db = tmp_path / "c.db"
    conn = store.connect(db)
    core = tmp_path / "brand-core.json"
    core.write_text(_json.dumps(doc.model_dump(), ensure_ascii=False), encoding="utf-8")
    bid = store.import_brand_core(conn, core)
    day = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
    store.record(conn, [
        (bid, "google_ads", "leads", day, 12),
        (bid, "google_ads", "cout_eur", day, 600),
    ])
    conn.close()

    body = html.unescape(TestClient(create_app(db)).get(f"/marque/salonlea-fr").text)
    assert "12" in body
    assert "50 €" in body.replace(" ", " ")   # 600 / 12
    assert "par acquisition" in body


# ------------------------------------------------------------ sécurité en ligne

import base64 as _b64


def _protected(tmp_path):
    return TestClient(create_app(tmp_path / "p.db", password="motdepasse"))


def _auth(user="admin", pw="motdepasse"):
    return {"Authorization": "Basic " + _b64.b64encode(f"{user}:{pw}".encode()).decode()}


def test_console_requires_the_password_when_one_is_set(tmp_path):
    c = _protected(tmp_path)
    assert c.get("/").status_code == 401
    assert c.get("/", headers=_auth(pw="faux")).status_code == 401
    assert c.get("/", headers=_auth()).status_code == 200


def test_health_check_is_public_and_says_nothing(tmp_path):
    r = _protected(tmp_path).get("/sante")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_decisions_from_another_site_are_refused(tmp_path):
    """Sans contrôle d'origine, une page tierce pourrait faire valider une dépense
    par un navigateur déjà connecté à la console."""
    db = tmp_path / "p.db"
    conn = store.connect(db)
    bid = store.add_brand(conn, slug="o", name="Oria", url="https://oria.fr")
    cur = conn.execute("INSERT INTO campaign (brand_id, channel, name, hard_cap_eur, created_at) VALUES (?, 'meta_ads', 'A', 100, ?)",
                       (bid, store.now()))
    conn.commit()
    aid = store.request_approval(conn, kind="depense", subject_table="campaign",
                                 subject_id=int(cur.lastrowid), brand_id=bid, summary="A", amount_eur=100)
    conn.close()
    c = TestClient(create_app(db, password="motdepasse"))

    evil = c.post(f"/validations/{aid}/valider", headers={**_auth(), "Origin": "https://evil.example"},
                  follow_redirects=False)
    assert evil.status_code == 403
    no_origin = c.post(f"/validations/{aid}/valider", headers=_auth(), follow_redirects=False)
    assert no_origin.status_code == 403
    assert store.get_approval(store.connect(db), aid)["state"] == "en_attente"

    ok = c.post(f"/validations/{aid}/valider", headers={**_auth(), "Origin": "http://testserver"},
                follow_redirects=False)
    assert ok.status_code == 303
    assert store.get_approval(store.connect(db), aid)["state"] == "approuve"
    assert store.get_approval(store.connect(db), aid)["decided_by"] == "console"


def test_approvals_page_lists_pending_requests_and_jobs(tmp_path):
    db = tmp_path / "p.db"
    conn = store.connect(db)
    bid = store.add_brand(conn, slug="o", name="Oria", url="https://oria.fr")
    cur = conn.execute("INSERT INTO content (brand_id, channel, created_at) VALUES (?, 'instagram', ?)",
                       (bid, store.now()))
    conn.commit()
    store.request_approval(conn, kind="publication", subject_table="content",
                           subject_id=int(cur.lastrowid), brand_id=bid, summary="Post du mardi")
    conn.close()
    body = text(TestClient(create_app(db)).get("/validations"))
    assert "Post du mardi" in body
    assert "Valider" in body and "Refuser" in body
    assert "collecter" in body and "resume" in body
