"""La console multi-marques.

Rendu côté serveur, volontairement : un seul langage dans tout le projet, et la
couche données survit intacte si l'interface est refaite plus tard.

Les écrans affichent l'état réel, y compris quand il est vide. Un canal non
connecté se voit ; un rapport sans données le dit. Une console qui cache ses
trous ne sert à rien.
"""

from __future__ import annotations

import base64
import binascii
import json
import secrets
import sqlite3
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
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


#: Chemins accessibles sans mot de passe. Le point de santé ne renvoie rien
#: d'autre que « ok » : Railway s'en sert pour savoir si le service vit.
PUBLIC_PATHS = frozenset({"/sante"})


def create_app(
    db_path: Path | str = store.DEFAULT_DB,
    *,
    password: str | None = None,
    user: str = "admin",
    worker: object | None = None,
) -> FastAPI:
    """La console. `password` protège tout sauf `/sante`. `worker` est un
    `autonomy.scheduler.Context` : s'il est fourni, le planificateur et l'écoute
    Telegram démarrent avec le serveur et s'arrêtent avec lui."""
    stop = threading.Event()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if worker is not None:
            from ..autonomy import scheduler

            scheduler.start(worker, stop)  # type: ignore[arg-type]
        yield
        stop.set()

    app = FastAPI(title="Agent Growth — console", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    db_path = Path(db_path)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        if password:
            if not _authorized(request.headers.get("authorization", ""), user, password):
                return Response("Authentification requise.", status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="Agent Growth", charset="UTF-8"'})
        # Les actions (POST) doivent venir de la console elle-même. Sans ce
        # contrôle, une page tierce pourrait faire valider une dépense par le
        # navigateur déjà connecté.
        if request.method == "POST" and not _same_origin(request):
            return Response("Requête refusée : origine inconnue.", status_code=403)
        return await call_next(request)

    @app.get("/sante")
    def health() -> JSONResponse:
        return JSONResponse({"ok": True})

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
            # Le résultat agrégé du portefeuille. C'est la première chose à
            # l'écran, parce que c'est la seule question qui compte.
            acquired = sum(r["outcome"]["acquired"] for r in rows)
            cost = sum(r["outcome"]["cost"] for r in rows)
            prev_acquired = sum(r["outcome"]["previous_acquired"] for r in rows)
            prev_cost = sum(r["outcome"]["previous_cost"] for r in rows)
            total = {
                "measured": any(r["outcome"]["measured"] for r in rows),
                "acquired": acquired,
                "previous_acquired": prev_acquired,
                "cost": cost,
                "cpa": (cost / acquired) if acquired else None,
                "previous_cpa": (prev_cost / prev_acquired) if prev_acquired else None,
            }
            return TEMPLATES.TemplateResponse(
                request,
                "portfolio.html",
                ctx(
                    rows=rows,
                    total=total,
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
                    outcome=store.outcome(conn, bid, days=days),
                    activity=store.activity(conn, bid, days=days),
                    last_collected=store.last_collected(conn, bid),
                    core=_load_core(brand),
                    pipeline=[(PIPELINE_LABELS[s], pipe.get(s, 0)) for s in PIPELINE_ORDER],
                    pipeline_total=sum(pipe.values()),
                    days=days,
                ),
            )
        finally:
            conn.close()

    @app.get("/validations", response_class=HTMLResponse)
    def approvals(request: Request) -> HTMLResponse:
        conn = db()
        try:
            return TEMPLATES.TemplateResponse(
                request,
                "approvals.html",
                ctx(
                    pending=store.pending_approvals(conn),
                    failures=store.recent_failures(conn, 8),
                    jobs=[(name, store.last_job_run(conn, name)) for name in _job_names()],
                ),
            )
        finally:
            conn.close()

    @app.post("/validations/{approval_id}/{verdict}")
    def decide(approval_id: int, verdict: str) -> Response:
        if verdict not in ("valider", "refuser"):
            return Response("Décision inconnue.", status_code=400)
        conn = db()
        try:
            store.decide(conn, approval_id, approve=(verdict == "valider"), by="console")
        finally:
            conn.close()
        return RedirectResponse("/validations", status_code=303)

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


def _authorized(header: str, user: str, password: str) -> bool:
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return False
    try:
        given_user, _, given_password = base64.b64decode(encoded).decode("utf-8").partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    # Comparaison à temps constant : la durée ne doit rien révéler du mot de passe.
    return secrets.compare_digest(given_user, user) & secrets.compare_digest(given_password, password)


def _same_origin(request: Request) -> bool:
    source = request.headers.get("origin") or request.headers.get("referer") or ""
    if not source:
        return False
    return urlparse(source).netloc == request.headers.get("host", "")


def _job_names() -> list[str]:
    from ..autonomy.scheduler import JOBS

    return [j.name for j in JOBS]


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
