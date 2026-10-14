"""La console multi-marques.

Rendu côté serveur, volontairement : un seul langage dans tout le projet, et la
couche données survit intacte si l'interface est refaite plus tard.

Les écrans affichent l'état réel, y compris quand il est vide. Un canal non
connecté se voit ; un rapport sans données le dit. Une console qui cache ses
trous ne sert à rien.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .. import store

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

CHANNEL_LABELS = store.CHANNELS

GATE_LABELS = {
    "ouvert": ("Disponible", "ok"),
    "revue": ("Revue d'app requise", "warn"),
    "manuel": ("Demande d'accès", "warn"),
}

STATE_LABELS = {
    "a_connecter": ("À connecter", "idle"),
    "connecte": ("Connecté", "ok"),
    "erreur": ("En erreur", "bad"),
    "desactive": ("Désactivé", "idle"),
    "disponible": ("Non connecté", "idle"),
}

PIPELINE_ORDER = ("trouve", "enrichi", "qualifie", "contacte", "repondu", "rdv", "gagne", "perdu", "exclu")
PIPELINE_LABELS = {
    "trouve": "Trouvés", "enrichi": "Enrichis", "qualifie": "Qualifiés",
    "contacte": "Contactés", "repondu": "Ont répondu", "rdv": "Rendez-vous",
    "gagne": "Gagnés", "perdu": "Perdus", "exclu": "Exclus",
}


def create_app(db_path: Path | str = store.DEFAULT_DB) -> FastAPI:
    app = FastAPI(title="Agent Growth — console", docs_url=None, redoc_url=None)
    db_path = Path(db_path)

    def db() -> sqlite3.Connection:
        return store.connect(db_path)

    def ctx(**extra: object) -> dict:
        """Le contexte commun à tous les écrans. Starlette ajoute `request`."""
        base: dict = {
            "channel_labels": CHANNEL_LABELS,
            "state_labels": STATE_LABELS,
            "gate_labels": GATE_LABELS,
        }
        base.update(extra)
        return base

    @app.get("/", response_class=HTMLResponse)
    def portfolio(request: Request, days: int = 30) -> HTMLResponse:
        conn = db()
        try:
            rows = store.portfolio(conn, days=days)
            money = store.revenue(conn)
            to_review = sum(r["to_review"] for r in rows)
            spend = sum(r["daily_spend_eur"] or 0 for r in rows)
            unconnected = sum(
                1 for r in rows for c in r["channels"] if c["state"] == "a_connecter"
            )
            return TEMPLATES.TemplateResponse(
                request,
                "portfolio.html",
                ctx(
                    rows=rows,
                    money=money,
                    days=days,
                    to_review=to_review,
                    daily_spend=spend,
                    unconnected=unconnected,
                    log=store.recent_log(conn, 8),
                ),
            )
        finally:
            conn.close()

    @app.get("/marque/{slug}", response_class=HTMLResponse)
    def brand_view(request: Request, slug: str, days: int = 30) -> HTMLResponse:
        conn = db()
        try:
            brand = store.get_brand(conn, slug)
            if brand is None:
                return TEMPLATES.TemplateResponse(
                    request, "missing.html", ctx(slug=slug), status_code=404
                )
            bid = int(brand["id"])
            pipe = store.pipeline(conn, bid)
            return TEMPLATES.TemplateResponse(
                request,
                "brand.html",
                ctx(
                    brand=brand,
                    sites=store.list_sites(conn, bid),
                    channels=store.list_channels(conn, bid),
                    totals=store.totals(conn, bid, days=days),
                    last_collected=store.last_collected(conn, bid),
                    core=_load_core(brand),
                    pipeline=[(PIPELINE_LABELS[s], pipe.get(s, 0)) for s in PIPELINE_ORDER],
                    pipeline_total=sum(pipe.values()),
                    days=days,
                ),
            )
        finally:
            conn.close()

    @app.get("/outils", response_class=HTMLResponse)
    def tools(request: Request) -> HTMLResponse:
        conn = db()
        try:
            store.seed_catalog(conn)
            by_cat: dict[str, list] = {}
            for row in store.list_integrations(conn):
                cfg = json.loads(row["config"] or "{}")
                by_cat.setdefault(row["category"], []).append({"row": row, "cfg": cfg})
            return TEMPLATES.TemplateResponse(
                request,
                "tools.html",
                ctx(
                    by_cat=by_cat,
                    categories={
                        "analytics": "Mesure",
                        "ads": "Régies publicitaires",
                        "social": "Réseaux et fiche Google",
                        "site": "Sites",
                        "email": "Envoi d'e-mails",
                        "enrichment": "Enrichissement",
                        "sourcing": "Sourcing de prospects",
                        "crm": "CRM",
                        "media": "Création visuelle",
                    },
                ),
            )
        finally:
            conn.close()

    return app


def _load_core(brand: sqlite3.Row) -> dict | None:
    """Charge la ligne éditoriale si `brand-core` a déjà tourné pour cette marque.

    Le chemin vient de la base (`core_path`), pas d'une convention relative au
    répertoire courant : la console doit s'ouvrir depuis n'importe où.
    """
    path = Path(brand["core_path"]) if brand["core_path"] else Path("brands") / brand["slug"] / "brand-core.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
