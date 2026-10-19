"""Accès à la base de la console.

Pas d'ORM : du SQL lisible, portable vers PostgreSQL le jour où la console
quitte le poste de travail. Les dates sont des chaînes ISO 8601, ce qui se
compare et se trie correctement en SQL comme en Python.

Une règle tenue partout ici : **aucun secret ne transite par cette base.**
`connected_account.secret_ref` ne contient qu'une référence vers le coffre.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")

#: Base par défaut. Dans `brands/`, donc ignorée par Git : ce sont des données clients.
DEFAULT_DB = Path("brands/console.db")

#: Canaux connus. La liste vit ici parce que la console, les connecteurs et le
#: calendrier doivent parler le même vocabulaire.
CHANNELS: dict[str, str] = {
    "seo": "SEO",
    "geo": "GEO (citations IA)",
    "site": "Site",
    "gmb": "Fiche Google",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "linkedin": "LinkedIn",
    "tiktok": "TikTok",
    "google_ads": "Google Ads",
    "meta_ads": "Meta Ads",
    "email": "E-mail",
}

#: Plateformes de site, et l'adaptateur d'écriture qui va avec (sites/).
#: « manuel » = pas d'API d'écriture : on prépare, l'humain colle.
PLATFORMS: dict[str, str] = {
    "wordpress": "api",
    "shopify": "api",
    "sur_mesure": "git",      # site développé et versionné sur GitHub
    "speedmedia": "manuel",   # CMS fermé des agences de voyage
    "wix": "manuel",
    "squarespace": "manuel",
    "webflow": "manuel",
    "inconnue": "manuel",
}

#: Canaux qui dépensent de l'argent : ils imposent un plafond et une validation.
PAID_CHANNELS = frozenset({"google_ads", "meta_ads"})

# Le vocabulaire des métriques est séparé en deux, et ce n'est pas cosmétique
# (docs/PREMIERS-PRINCIPES.md § 5). Un client achète des clients de plus à un
# coût connu : c'est le **résultat**. Les clics, visites et abonnés sont de
# l'**activité** — utiles pour comprendre pourquoi, jamais pour dire si ça
# marche. Un écran qui ouvre sur de l'activité répond à la mauvaise question.

#: Ce qui compte comme un résultat acquis.
ACQUISITION_METRICS = frozenset({"leads", "clients", "ventes", "rdv"})

#: Le chiffre d'affaires attribué.
REVENUE_METRICS = frozenset({"ca_eur"})

#: Ce que ça a coûté.
COST_METRICS = frozenset({"cout_eur"})

#: Tout ce qui décide du haut de l'écran.
OUTCOME_METRICS = ACQUISITION_METRICS | REVENUE_METRICS | COST_METRICS


def is_outcome(metric: str) -> bool:
    return metric in OUTCOME_METRICS

#: Le `brand-core` raisonne en familles de canaux (« social », « ads »), parce
#: qu'une stratégie se pense comme ça. La console a besoin de canaux concrets,
#: parce qu'un connecteur se branche sur une plateforme précise. Cette table
#: traduit les uns en les autres — et ce qu'elle produit est une **proposition**
#: que l'humain ajuste, pas une vérité.
CORE_CHANNEL_MAP: dict[str, tuple[str, ...]] = {
    "seo": ("seo",),
    "geo": ("geo",),
    "site": ("site",),
    "gmb": ("gmb",),
    "email": ("email",),
    "social": ("instagram",),              # le plus courant chez une TPE
    "ads": ("google_ads", "meta_ads"),
    "outbound": ("email",),
    "influence": (),                        # aucun canal technique à brancher
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    """Ouvre la base, la crée si besoin, et applique le schéma."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Plusieurs fils écrivent (console, planificateur, Telegram) : le journal
    # WAL laisse lire pendant qu'on écrit, et l'attente évite les « database is
    # locked ». Chaque fil ouvre sa propre connexion.
    conn = sqlite3.connect(path, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    _migrate(conn)
    seed_catalog(conn)
    return conn


#: Colonnes ajoutées après coup. `CREATE TABLE IF NOT EXISTS` ne les ajoute pas
#: à une base qui existe déjà : sans ça, une mise à jour du code casse la base
#: de production. Chaque entrée est `(table, colonne, définition)`.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("brand", "core_path", "TEXT NOT NULL DEFAULT ''"),
    ("site", "secret_ref", "TEXT NOT NULL DEFAULT ''"),
    ("site", "config", "TEXT NOT NULL DEFAULT '{}'"),
    ("content", "notes", "TEXT NOT NULL DEFAULT ''"),
    ("content", "score", "REAL"),
)


def _migrate(conn: sqlite3.Connection) -> list[str]:
    """Ajoute les colonnes manquantes. Sans effet sur une base à jour."""
    applied: list[str] = []
    for table, column, ddl in _ADDED_COLUMNS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            applied.append(f"{table}.{column}")
    if applied:
        conn.commit()
    return applied


# --------------------------------------------------------------------------- #
# Marques
# --------------------------------------------------------------------------- #

def add_brand(
    conn: sqlite3.Connection,
    *,
    slug: str,
    name: str,
    url: str,
    kind: str = "interne",
    plan: str | None = None,
    monthly_fee_eur: float | None = None,
    notes: str = "",
) -> int:
    cur = conn.execute(
        """INSERT INTO brand (slug, name, url, kind, plan, monthly_fee_eur, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (slug, name, url, kind, plan, monthly_fee_eur, notes, now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_brands(conn: sqlite3.Connection, *, include_archived: bool = False) -> list[sqlite3.Row]:
    sql = "SELECT * FROM brand"
    if not include_archived:
        sql += " WHERE status != 'archive'"
    sql += " ORDER BY kind, name"
    return conn.execute(sql).fetchall()


def get_brand(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM brand WHERE slug = ?", (slug,)).fetchone()


# --------------------------------------------------------------------------- #
# Sites et canaux
# --------------------------------------------------------------------------- #

def add_site(
    conn: sqlite3.Connection,
    brand_id: int,
    url: str,
    *,
    platform: str = "inconnue",
    page_count: int | None = None,
    write_access: str | None = None,
    secret_ref: str = "",
    config: dict | None = None,
) -> int:
    if platform not in PLATFORMS:
        raise ValueError(f"Plateforme inconnue : {platform}. Connues : {', '.join(PLATFORMS)}")
    _check_secret_ref(secret_ref)
    access = write_access or (PLATFORMS[platform] if secret_ref or PLATFORMS[platform] == "manuel" else "aucun")
    conn.execute(
        """INSERT INTO site (brand_id, url, platform, page_count, write_access, secret_ref, config)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (brand_id, url) DO UPDATE SET
               platform = excluded.platform, write_access = excluded.write_access,
               secret_ref = excluded.secret_ref, config = excluded.config,
               page_count = COALESCE(excluded.page_count, site.page_count)""",
        (brand_id, url, platform, page_count, access, secret_ref,
         json.dumps(config or {}, ensure_ascii=False)),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM site WHERE brand_id = ? AND url = ?", (brand_id, url)).fetchone()
    return int(row["id"])


def get_site(conn: sqlite3.Connection, site_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM site WHERE id = ?", (site_id,)).fetchone()


def add_channel(conn: sqlite3.Connection, brand_id: int, kind: str, *, handle: str = "") -> None:
    if kind not in CHANNELS:
        raise ValueError(f"Canal inconnu : {kind}. Connus : {', '.join(CHANNELS)}")
    conn.execute(
        "INSERT OR IGNORE INTO channel (brand_id, kind, handle) VALUES (?, ?, ?)",
        (brand_id, kind, handle),
    )
    conn.commit()


def list_channels(conn: sqlite3.Connection, brand_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM channel WHERE brand_id = ? ORDER BY kind", (brand_id,)
    ).fetchall()


def list_sites(conn: sqlite3.Connection, brand_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM site WHERE brand_id = ? ORDER BY url", (brand_id,)).fetchall()


# --------------------------------------------------------------------------- #
# Mesures — le cœur du reporting
# --------------------------------------------------------------------------- #

def record(
    conn: sqlite3.Connection,
    rows: Iterable[tuple[int, str, str, str, float]],
) -> int:
    """Enregistre des mesures `(brand_id, canal, métrique, jour, valeur)`.

    Idempotent : rejouer une collecte écrase la valeur du même jour au lieu de
    la dupliquer. C'est ce qui permet de relancer un connecteur sans crainte.
    """
    rows = list(rows)
    conn.executemany(
        """INSERT INTO measure (brand_id, channel, metric, day, value)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (brand_id, channel, metric, day) DO UPDATE SET value = excluded.value""",
        rows,
    )
    conn.commit()
    return len(rows)


def series(
    conn: sqlite3.Connection, brand_id: int, channel: str, metric: str, *, days: int = 30
) -> list[sqlite3.Row]:
    since = (date.today() - timedelta(days=days)).isoformat()
    return conn.execute(
        """SELECT day, value FROM measure
           WHERE brand_id = ? AND channel = ? AND metric = ? AND day >= ?
           ORDER BY day""",
        (brand_id, channel, metric, since),
    ).fetchall()


def totals(
    conn: sqlite3.Connection, brand_id: int, *, days: int = 30
) -> list[sqlite3.Row]:
    """Somme par canal et par métrique sur la période, avec la période précédente.

    Deux fenêtres dans une seule requête : c'est ce qui donne la variation
    affichée dans la console sans aller-retour supplémentaire.
    """
    end = date.today()
    start = end - timedelta(days=days)
    prev_start = start - timedelta(days=days)
    return conn.execute(
        """SELECT channel, metric,
                  SUM(CASE WHEN day >= ? THEN value ELSE 0 END)  AS current,
                  SUM(CASE WHEN day <  ? THEN value ELSE 0 END)  AS previous
           FROM measure
           WHERE brand_id = ? AND day >= ?
           GROUP BY channel, metric
           ORDER BY channel, metric""",
        (start.isoformat(), start.isoformat(), brand_id, prev_start.isoformat()),
    ).fetchall()


def outcome(conn: sqlite3.Connection, brand_id: int, *, days: int = 30) -> dict:
    """Le résultat d'une marque : combien acquis, à quel coût, et l'évolution.

    C'est la seule chose qu'un client ne peut pas obtenir gratuitement ailleurs,
    donc c'est ce qui s'affiche en premier. Renvoie `measured = False` quand rien
    n'a été mesuré — auquel cas la console le dit au lieu de remplir l'écran
    avec de l'activité.
    """
    end = date.today()
    start = end - timedelta(days=days)
    prev_start = start - timedelta(days=days)

    def window(metrics: frozenset[str], since: str, until: str | None) -> float:
        placeholders = ",".join("?" * len(metrics))
        sql = (
            f"SELECT COALESCE(SUM(value), 0) AS s FROM measure "
            f"WHERE brand_id = ? AND metric IN ({placeholders}) AND day >= ?"
        )
        args: list[object] = [brand_id, *sorted(metrics), since]
        if until is not None:
            sql += " AND day < ?"
            args.append(until)
        return float(conn.execute(sql, args).fetchone()["s"])

    s_iso, p_iso = start.isoformat(), prev_start.isoformat()
    acquired = window(ACQUISITION_METRICS, s_iso, None)
    cost = window(COST_METRICS, s_iso, None)
    revenue = window(REVENUE_METRICS, s_iso, None)
    prev_acquired = window(ACQUISITION_METRICS, p_iso, s_iso)
    prev_cost = window(COST_METRICS, p_iso, s_iso)

    return {
        "measured": bool(acquired or cost or revenue),
        "acquired": acquired,
        "previous_acquired": prev_acquired,
        "cost": cost,
        "previous_cost": prev_cost,
        "revenue": revenue,
        # Coût par acquisition. None plutôt que zéro : « on ne sait pas » et
        # « c'est gratuit » ne doivent jamais s'afficher pareil.
        "cpa": (cost / acquired) if acquired else None,
        "previous_cpa": (prev_cost / prev_acquired) if prev_acquired else None,
        "roas": (revenue / cost) if cost else None,
    }


def activity(conn: sqlite3.Connection, brand_id: int, *, days: int = 30) -> list[sqlite3.Row]:
    """Les métriques de diagnostic, hors résultat."""
    return [r for r in totals(conn, brand_id, days=days) if not is_outcome(r["metric"])]


def last_collected(conn: sqlite3.Connection, brand_id: int) -> str | None:
    row = conn.execute(
        "SELECT MAX(day) AS d FROM measure WHERE brand_id = ?", (brand_id,)
    ).fetchone()
    return row["d"] if row else None


# --------------------------------------------------------------------------- #
# Vue portefeuille
# --------------------------------------------------------------------------- #

def portfolio(conn: sqlite3.Connection, *, days: int = 30) -> list[dict]:
    """Une ligne par marque, avec de quoi remplir la vue d'ensemble."""
    out: list[dict] = []
    for brand in list_brands(conn):
        channels = list_channels(conn, brand["id"])
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM content WHERE brand_id = ? AND state = 'a_valider'",
            (brand["id"],),
        ).fetchone()["n"]
        live_spend = conn.execute(
            """SELECT COALESCE(SUM(daily_budget_eur), 0) AS s FROM campaign
               WHERE brand_id = ? AND state = 'active'""",
            (brand["id"],),
        ).fetchone()["s"]
        out.append(
            {
                "brand": brand,
                "channels": channels,
                "connected": sum(1 for c in channels if c["state"] == "connecte"),
                "to_review": pending,
                "daily_spend_eur": live_spend,
                "last_collected": last_collected(conn, brand["id"]),
                # Le résultat d'abord, l'activité ensuite — dans cet ordre
                # jusque dans la structure de données.
                "outcome": outcome(conn, brand["id"], days=days),
                "activity": activity(conn, brand["id"], days=days),
            }
        )
    return out


def revenue(conn: sqlite3.Connection) -> dict[str, float]:
    row = conn.execute(
        """SELECT COALESCE(SUM(monthly_fee_eur), 0) AS mrr, COUNT(*) AS n
           FROM brand WHERE kind = 'client' AND status = 'actif'"""
    ).fetchone()
    return {"mrr": row["mrr"], "clients": row["n"]}


# --------------------------------------------------------------------------- #
# Journal
# --------------------------------------------------------------------------- #

def log(
    conn: sqlite3.Connection,
    *,
    action: str,
    actor: str = "agent",
    brand_id: int | None = None,
    rationale: str = "",
    payload: object = None,
) -> None:
    conn.execute(
        """INSERT INTO decision_log (brand_id, at, actor, action, rationale, payload)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            brand_id,
            now(),
            actor,
            action,
            rationale,
            json.dumps(payload, ensure_ascii=False) if payload is not None else "",
        ),
    )
    conn.commit()


def recent_log(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT d.*, b.name AS brand_name FROM decision_log d
           LEFT JOIN brand b ON b.id = d.brand_id
           ORDER BY d.at DESC LIMIT ?""",
        (limit,),
    ).fetchall()


# --------------------------------------------------------------------------- #
# Import depuis un brand-core
# --------------------------------------------------------------------------- #

def import_brand_core(conn: sqlite3.Connection, path: Path | str) -> int:
    """Enregistre une marque depuis son `brand-core.json`.

    Les canaux ne sont pas demandés : ils se déduisent des angles
    différenciants, qui disent déjà sur quels canaux la marque doit jouer.
    C'est le premier bénéfice concret du contrat `brand-core`.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    core = data["core"]
    url = data["brand_url"]
    slug = _slugify(url)

    existing = get_brand(conn, slug)
    if existing:
        brand_id = int(existing["id"])
    else:
        brand_id = add_brand(conn, slug=slug, name=core["brand_name"], url=url)

    add_site(conn, brand_id, url)

    families = {"site", "seo", "geo"}
    for angle in core.get("differentiating_angles", []):
        families.update(angle.get("best_channels", []))
    for opp in core.get("opportunities", []):
        families.add(opp.get("channel", ""))

    wanted: set[str] = set()
    for family in families:
        wanted.update(CORE_CHANNEL_MAP.get(family, ()))

    for kind in sorted(wanted):
        add_channel(conn, brand_id, kind)

    conn.execute("UPDATE brand SET core_path = ? WHERE id = ?", (str(Path(path)), brand_id))
    conn.commit()

    log(
        conn,
        brand_id=brand_id,
        actor="agent",
        action="import brand-core",
        rationale=f"{len(wanted)} canaux proposés depuis {len(families)} familles — à ajuster",
        payload={"source": str(path), "schema_version": data.get("schema_version"),
                 "familles": sorted(f for f in families if f)},
    )
    return brand_id


def _slugify(url: str) -> str:
    import re
    import unicodedata

    host = re.sub(r"^https?://", "", url).split("/")[0]
    host = re.sub(r"^www\.", "", host)
    ascii_host = unicodedata.normalize("NFKD", host).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_host.lower()).strip("-") or "marque"


# --------------------------------------------------------------------------- #
# Catalogue des outils branchables
# --------------------------------------------------------------------------- #
# Ce catalogue est la carte du territoire : il dit ce qu'on peut brancher, ce
# que ça demande, et si une revue d'application est nécessaire. Les colonnes
# `auth` et `gate` encodent le travail de vérification fait dans PLATEFORME.md,
# pour qu'on n'ait pas à le redécouvrir à chaque connecteur.
#
# `gate` : "ouvert" = disponible tout de suite sur ses propres comptes.
#          "revue"  = revue d'application nécessaire pour les comptes d'autrui.
#          "manuel" = demande d'accès à déposer, avec délai.

CATALOG: tuple[dict[str, str], ...] = (
    # Mesure
    {"slug": "ga4", "name": "Google Analytics 4", "category": "analytics", "auth": "oauth", "gate": "ouvert"},
    {"slug": "search_console", "name": "Google Search Console", "category": "analytics", "auth": "oauth", "gate": "ouvert"},
    {"slug": "matomo", "name": "Matomo", "category": "analytics", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "plausible", "name": "Plausible", "category": "analytics", "auth": "cle_api", "gate": "ouvert"},
    # Régies
    {"slug": "google_ads", "name": "Google Ads", "category": "ads", "auth": "oauth", "gate": "ouvert"},
    {"slug": "meta_ads", "name": "Meta Ads", "category": "ads", "auth": "jeton_systeme", "gate": "revue"},
    {"slug": "linkedin_ads", "name": "LinkedIn Ads", "category": "ads", "auth": "oauth", "gate": "revue"},
    {"slug": "tiktok_ads", "name": "TikTok Ads", "category": "ads", "auth": "oauth", "gate": "revue"},
    # Réseaux
    {"slug": "meta_pages", "name": "Instagram et Facebook", "category": "social", "auth": "oauth", "gate": "revue"},
    {"slug": "linkedin_pages", "name": "Pages LinkedIn", "category": "social", "auth": "oauth", "gate": "revue"},
    {"slug": "tiktok_content", "name": "TikTok", "category": "social", "auth": "oauth", "gate": "revue"},
    {"slug": "gmb", "name": "Fiche Google Business", "category": "social", "auth": "oauth", "gate": "manuel"},
    {"slug": "buffer", "name": "Buffer", "category": "social", "auth": "cle_api", "gate": "ouvert"},
    # Site
    {"slug": "wordpress", "name": "WordPress", "category": "site", "auth": "mot_de_passe_app", "gate": "ouvert"},
    {"slug": "shopify", "name": "Shopify", "category": "site", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "webflow", "name": "Webflow", "category": "site", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "git", "name": "Dépôt Git (site statique)", "category": "site", "auth": "jeton", "gate": "ouvert"},
    # Envoi
    {"slug": "brevo", "name": "Brevo", "category": "email", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "resend", "name": "Resend", "category": "email", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "lemlist", "name": "Lemlist", "category": "email", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "instantly", "name": "Instantly", "category": "email", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "smartlead", "name": "Smartlead", "category": "email", "auth": "cle_api", "gate": "ouvert"},
    # Enrichissement
    {"slug": "dropcontact", "name": "Dropcontact", "category": "enrichment", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "apollo", "name": "Apollo", "category": "enrichment", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "hunter", "name": "Hunter", "category": "enrichment", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "clay", "name": "Clay", "category": "enrichment", "auth": "cle_api", "gate": "ouvert"},
    # Sourcing
    {"slug": "google_places", "name": "Google Places", "category": "sourcing", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "pappers", "name": "Pappers (registre français)", "category": "sourcing", "auth": "cle_api", "gate": "ouvert"},
    # CRM
    {"slug": "hubspot", "name": "HubSpot", "category": "crm", "auth": "oauth", "gate": "ouvert"},
    {"slug": "pipedrive", "name": "Pipedrive", "category": "crm", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "gohighlevel", "name": "GoHighLevel", "category": "crm", "auth": "oauth", "gate": "ouvert"},
    {"slug": "airtable", "name": "Airtable", "category": "crm", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "notion", "name": "Notion", "category": "crm", "auth": "oauth", "gate": "ouvert"},
    # Création
    {"slug": "kling", "name": "Kling (vidéo)", "category": "media", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "veo", "name": "Veo (vidéo)", "category": "media", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "runway", "name": "Runway (vidéo)", "category": "media", "auth": "cle_api", "gate": "ouvert"},
    {"slug": "flux", "name": "Flux (image)", "category": "media", "auth": "cle_api", "gate": "ouvert"},
)

CATALOG_BY_SLUG = {t["slug"]: t for t in CATALOG}


def seed_catalog(conn: sqlite3.Connection) -> int:
    """Inscrit le catalogue comme « disponible ». Idempotent."""
    conn.executemany(
        """INSERT INTO integration (slug, name, category, config) VALUES (?, ?, ?, ?)
           ON CONFLICT (slug) DO UPDATE SET name = excluded.name, category = excluded.category""",
        [(t["slug"], t["name"], t["category"], json.dumps({"auth": t["auth"], "gate": t["gate"]}))
         for t in CATALOG],
    )
    conn.commit()
    return len(CATALOG)


def list_integrations(conn: sqlite3.Connection, *, category: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM integration"
    args: Sequence[object] = ()
    if category:
        sql += " WHERE category = ?"
        args = (category,)
    return conn.execute(sql + " ORDER BY category, name", args).fetchall()


def _check_secret_ref(secret_ref: str) -> None:
    """Une référence est un NOM de variable : majuscules, chiffres, soulignés.

    Tout le reste — une clé collée par erreur, une URL avec un jeton — est
    refusé avant d'atteindre la base.
    """
    import re

    if secret_ref and not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", secret_ref):
        raise ValueError(
            "La référence doit être un nom de variable d'environnement "
            "(ex. « BREVO_API_KEY »), pas la valeur du secret."
        )


def connect_integration(conn: sqlite3.Connection, slug: str, *, secret_ref: str) -> None:
    """Marque un outil comme connecté. `secret_ref` est un nom de variable
    d'environnement ou une clé de coffre — **jamais** le secret."""
    _check_secret_ref(secret_ref)
    cur = conn.execute(
        """UPDATE integration SET state = 'connecte', secret_ref = ?, connected_at = ?, last_error = ''
           WHERE slug = ?""",
        (secret_ref, now(), slug),
    )
    if cur.rowcount == 0:
        raise KeyError(f"Outil inconnu : {slug}")
    conn.commit()


# --------------------------------------------------------------------------- #
# Prospection sortante
# --------------------------------------------------------------------------- #

def add_prospect(
    conn: sqlite3.Connection,
    brand_id: int,
    *,
    company: str,
    source: str,
    source_detail: str = "",
    email: str = "",
    contact_name: str = "",
    role: str = "",
    website: str = "",
    linkedin: str = "",
    icp_fit: float | None = None,
    icp_rationale: str = "",
) -> int:
    """Ajoute un prospect. `source` est obligatoire : sans origine tracée, on
    n'a pas le droit de le contacter (RGPD)."""
    if not source.strip():
        raise ValueError("L'origine du prospect est obligatoire (RGPD).")
    stamp = now()
    cur = conn.execute(
        """INSERT INTO prospect (brand_id, company, website, contact_name, role, email,
                                 linkedin, source, source_detail, icp_fit, icp_rationale,
                                 created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (brand_id, email) WHERE email != '' DO UPDATE SET
               updated_at = excluded.updated_at,
               icp_fit = COALESCE(excluded.icp_fit, prospect.icp_fit)""",
        (brand_id, company, website, contact_name, role, email, linkedin,
         source, source_detail, icp_fit, icp_rationale, stamp, stamp),
    )
    conn.commit()
    return int(cur.lastrowid)


def opt_out(conn: sqlite3.Connection, email: str) -> int:
    """Droit d'opposition. S'applique à **toutes** les marques d'un coup : une
    personne qui se désinscrit ne doit jamais réapparaître ailleurs."""
    cur = conn.execute(
        "UPDATE prospect SET opted_out = 1, state = 'exclu', updated_at = ? WHERE email = ?",
        (now(), email),
    )
    conn.execute(
        """UPDATE outreach SET state = 'annule'
           WHERE state IN ('prevu', 'a_valider')
             AND prospect_id IN (SELECT id FROM prospect WHERE email = ?)""",
        (email,),
    )
    conn.commit()
    return cur.rowcount


def contactable(conn: sqlite3.Connection, brand_id: int, *, min_fit: float = 0.0) -> list[sqlite3.Row]:
    """Les prospects qu'on a le droit de contacter. Un seul endroit décide, pour
    qu'aucun chemin d'envoi ne puisse contourner l'opposition."""
    return conn.execute(
        """SELECT * FROM prospect
           WHERE brand_id = ? AND opted_out = 0 AND email != ''
             AND state IN ('enrichi', 'qualifie')
             AND COALESCE(icp_fit, 0) >= ?
           ORDER BY COALESCE(icp_fit, 0) DESC""",
        (brand_id, min_fit),
    ).fetchall()


def pipeline(conn: sqlite3.Connection, brand_id: int) -> dict[str, int]:
    rows = conn.execute(
        "SELECT state, COUNT(*) AS n FROM prospect WHERE brand_id = ? GROUP BY state",
        (brand_id,),
    ).fetchall()
    return {r["state"]: r["n"] for r in rows}



# --------------------------------------------------------------------------- #
# Autonomie : la file de validation
# --------------------------------------------------------------------------- #
# Ce que décider fait à l'objet validé. Une seule table de transitions : aucun
# autre endroit du code ne fait avancer un contenu, une campagne, un envoi ou
# une modification de site après une décision.

APPROVE_TRANSITIONS: dict[str, tuple[str, str]] = {
    "content": ("a_valider", "valide"),
    "campaign": ("a_valider", "active"),
    "outreach": ("a_valider", "prevu"),
    "site_change": ("a_valider", "approuve"),
}
REFUSE_TRANSITIONS: dict[str, tuple[str, str]] = {
    "content": ("a_valider", "rejete"),
    "campaign": ("a_valider", "brouillon"),
    "outreach": ("a_valider", "annule"),
    "site_change": ("a_valider", "refuse"),
}

#: Durée de validité d'une demande, par nature. Une dépense validée trop tard
#: s'applique à un contexte qui n'existe plus.
APPROVAL_TTL_HOURS: dict[str, int] = {"depense": 48, "contact": 72, "publication": 72, "site": 168}


def request_approval(
    conn: sqlite3.Connection,
    *,
    kind: str,
    subject_table: str,
    subject_id: int,
    summary: str,
    brand_id: int | None = None,
    detail: str = "",
    amount_eur: float | None = None,
    channel: str = "*",
) -> int | None:
    """Demande une validation, ou l'accorde d'office si une règle automatique
    couvre ce cas. Renvoie l'identifiant de la demande, ou `None` si elle a été
    accordée automatiquement.

    L'objet passe en `a_valider` ici, dans la même transaction : il ne peut pas
    exister de demande pour un objet qui n'attend rien.
    """
    if subject_table not in APPROVE_TRANSITIONS:
        raise ValueError(f"Objet non validable : {subject_table}")
    conn.execute(
        f"UPDATE {subject_table} SET state = 'a_valider' WHERE id = ?", (subject_id,)
    )

    rule = _auto_rule(conn, brand_id, kind, channel, amount_eur)
    if rule is not None:
        _transition(conn, subject_table, subject_id, APPROVE_TRANSITIONS)
        log(conn, brand_id=brand_id, actor="agent", action=f"validation automatique : {kind}",
            rationale=f"règle n°{rule} — {summary}",
            payload={"subject": subject_table, "id": subject_id, "amount_eur": amount_eur})
        conn.commit()
        return None

    expires = (datetime.now(timezone.utc) + timedelta(hours=APPROVAL_TTL_HOURS[kind])).isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO approval (brand_id, kind, subject_table, subject_id, summary, detail,
                                 amount_eur, requested_at, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (brand_id, kind, subject_table, subject_id, summary, detail, amount_eur, now(), expires),
    )
    conn.commit()
    return int(cur.lastrowid)


def decide(conn: sqlite3.Connection, approval_id: int, *, approve: bool, by: str) -> bool:
    """Applique une décision. Renvoie False si la demande n'est plus en attente.

    L'idempotence est volontaire : un double appui sur « Valider » dans
    Telegram ne doit jamais lancer deux fois une dépense.
    """
    row = conn.execute(
        "SELECT * FROM approval WHERE id = ? AND state = 'en_attente'", (approval_id,)
    ).fetchone()
    if row is None:
        return False
    if row["expires_at"] and row["expires_at"] < now():
        # Expirée : on la clôt ET on libère l'objet, sinon il resterait bloqué
        # en « à valider » sans plus aucune demande pour le débloquer.
        conn.execute("UPDATE approval SET state = 'expire' WHERE id = ?", (approval_id,))
        _transition(conn, row["subject_table"], row["subject_id"], REFUSE_TRANSITIONS)
        conn.commit()
        return False

    cur = conn.execute(
        """UPDATE approval SET state = ?, decided_at = ?, decided_by = ?
           WHERE id = ? AND state = 'en_attente'""",
        ("approuve" if approve else "refuse", now(), by, approval_id),
    )
    if cur.rowcount != 1:      # décidé entre-temps par un autre canal
        conn.rollback()
        return False
    _transition(conn, row["subject_table"], row["subject_id"],
                APPROVE_TRANSITIONS if approve else REFUSE_TRANSITIONS)
    log(conn, brand_id=row["brand_id"], actor="humain",
        action=f"{'validé' if approve else 'refusé'} : {row['kind']}",
        rationale=row["summary"], payload={"approval": approval_id, "par": by})
    conn.commit()
    return True


def expire_stale(conn: sqlite3.Connection) -> int:
    """Expire les demandes dépassées et remet leur objet en brouillon."""
    stale = conn.execute(
        "SELECT * FROM approval WHERE state = 'en_attente' AND expires_at < ?", (now(),)
    ).fetchall()
    for row in stale:
        conn.execute("UPDATE approval SET state = 'expire' WHERE id = ?", (row["id"],))
        _transition(conn, row["subject_table"], row["subject_id"], REFUSE_TRANSITIONS)
    conn.commit()
    return len(stale)


def pending_approvals(conn: sqlite3.Connection, *, unnotified_only: bool = False) -> list[sqlite3.Row]:
    sql = """SELECT a.*, b.name AS brand_name FROM approval a
             LEFT JOIN brand b ON b.id = a.brand_id
             WHERE a.state = 'en_attente'"""
    if unnotified_only:
        sql += " AND a.notified_ref = ''"
    return conn.execute(sql + " ORDER BY a.requested_at", ()).fetchall()


def mark_notified(conn: sqlite3.Connection, approval_id: int, ref: str) -> None:
    conn.execute("UPDATE approval SET notified_ref = ? WHERE id = ?", (ref, approval_id))
    conn.commit()


def get_approval(conn: sqlite3.Connection, approval_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT a.*, b.name AS brand_name FROM approval a
           LEFT JOIN brand b ON b.id = a.brand_id WHERE a.id = ?""",
        (approval_id,),
    ).fetchone()


def add_auto_rule(
    conn: sqlite3.Connection, brand_id: int, kind: str, *, channel: str = "*",
    max_eur: float | None = None,
) -> int:
    """Active la validation automatique pour un cas précis. Une dépense
    automatique sans plafond est refusée par le schéma lui-même."""
    cur = conn.execute(
        """INSERT INTO auto_rule (brand_id, kind, channel, max_eur, created_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (brand_id, kind, channel) DO UPDATE SET
               max_eur = excluded.max_eur, enabled = 1""",
        (brand_id, kind, channel, max_eur, now()),
    )
    log(conn, brand_id=brand_id, actor="humain", action=f"validation automatique activée : {kind}",
        rationale=f"canal {channel}" + (f", plafond {max_eur:.0f} €" if max_eur is not None else ""))
    conn.commit()
    return int(cur.lastrowid)


def _auto_rule(conn: sqlite3.Connection, brand_id: int | None, kind: str,
               channel: str, amount_eur: float | None) -> int | None:
    if brand_id is None:
        return None
    row = conn.execute(
        """SELECT id, max_eur FROM auto_rule
           WHERE brand_id = ? AND kind = ? AND enabled = 1 AND channel IN (?, '*')
           ORDER BY channel = '*' LIMIT 1""",
        (brand_id, kind, channel),
    ).fetchone()
    if row is None:
        return None
    if row["max_eur"] is not None and (amount_eur is None or amount_eur > row["max_eur"]):
        return None        # au-dessus du plafond, ou montant inconnu : un humain décide
    return int(row["id"])


def _transition(conn: sqlite3.Connection, table: str, subject_id: int,
                transitions: dict[str, tuple[str, str]]) -> None:
    before, after = transitions[table]
    conn.execute(f"UPDATE {table} SET state = ? WHERE id = ? AND state = ?",
                 (after, subject_id, before))


# --------------------------------------------------------------------------- #
# Modifications de site
# --------------------------------------------------------------------------- #

def propose_site_change(
    conn: sqlite3.Connection, site_id: int, *, kind: str, title: str, body: str,
    target: str = "", slug: str = "", meta: dict | None = None, ai_generated: bool = True,
) -> tuple[int, int | None]:
    """Propose une modification et demande sa validation. Rien ne touche le
    site avant le « oui ». Renvoie (modification, demande)."""
    site = get_site(conn, site_id)
    if site is None:
        raise KeyError(f"Site inconnu : {site_id}")
    cur = conn.execute(
        """INSERT INTO site_change (brand_id, site_id, kind, target, title, body, slug, meta,
                                    ai_generated, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (site["brand_id"], site_id, kind, target, title, body, slug,
         json.dumps(meta or {}, ensure_ascii=False), int(ai_generated), now()),
    )
    change_id = int(cur.lastrowid)
    verb = "Créer" if kind == "page_create" else "Modifier"
    approval_id = request_approval(
        conn, kind="site", subject_table="site_change", subject_id=change_id,
        brand_id=site["brand_id"], channel="site",
        summary=f"{verb} la page « {title} » sur {site['url']}",
        detail=body[:600],
    )
    return change_id, approval_id


def site_changes(conn: sqlite3.Connection, state: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM site_change WHERE state = ? ORDER BY created_at", (state,)
    ).fetchall()


def finish_site_change(conn: sqlite3.Connection, change_id: int, *, state: str, result: str) -> None:
    conn.execute(
        "UPDATE site_change SET state = ?, result = ?, applied_at = ? WHERE id = ?",
        (state, result, now(), change_id),
    )
    conn.commit()


# --------------------------------------------------------------------------- #
# Planificateur
# --------------------------------------------------------------------------- #

def job_started(conn: sqlite3.Connection, job: str) -> int:
    cur = conn.execute("INSERT INTO job_run (job, started_at) VALUES (?, ?)", (job, now()))
    conn.commit()
    return int(cur.lastrowid)


def job_finished(conn: sqlite3.Connection, run_id: int, *, ok: bool, detail: str = "") -> None:
    conn.execute(
        "UPDATE job_run SET finished_at = ?, ok = ?, detail = ? WHERE id = ?",
        (now(), int(ok), detail[:2000], run_id),
    )
    conn.commit()


def last_job_run(conn: sqlite3.Connection, job: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM job_run WHERE job = ? ORDER BY started_at DESC, id DESC LIMIT 1", (job,)
    ).fetchone()


def recent_failures(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM job_run WHERE ok = 0 ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()



# --------------------------------------------------------------------------- #
# Travaux longs
# --------------------------------------------------------------------------- #

def task_started(conn: sqlite3.Connection, *, kind: str, label: str, brand_id: int | None) -> int:
    cur = conn.execute(
        "INSERT INTO task (brand_id, kind, label, created_at) VALUES (?, ?, ?, ?)",
        (brand_id, kind, label, now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def task_finished(conn: sqlite3.Connection, task_id: int, *, ok: bool, detail: str) -> None:
    conn.execute(
        "UPDATE task SET state = ?, detail = ?, finished_at = ? WHERE id = ?",
        ("termine" if ok else "echec", detail[:2000], now(), task_id),
    )
    conn.commit()


def recent_tasks(conn: sqlite3.Connection, *, brand_ids: set[int] | None = None, limit: int = 20) -> list[sqlite3.Row]:
    rows = conn.execute(
        """SELECT t.*, b.name AS brand_name, b.slug AS brand_slug FROM task t
           LEFT JOIN brand b ON b.id = t.brand_id ORDER BY t.id DESC LIMIT ?""",
        (limit * 3 if brand_ids is not None else limit,),
    ).fetchall()
    if brand_ids is not None:
        rows = [r for r in rows if r["brand_id"] in brand_ids][:limit]
    return rows


# --------------------------------------------------------------------------- #
# Contenus
# --------------------------------------------------------------------------- #

def add_content(conn: sqlite3.Connection, brand_id: int, *, channel: str, title: str, body: str,
                pillar: str = "", scheduled_for: str | None = None, notes: str = "",
                score: float | None = None, state: str = "genere") -> int:
    cur = conn.execute(
        """INSERT INTO content (brand_id, channel, pillar, scheduled_for, state, title, body,
                                notes, score, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (brand_id, channel, pillar, scheduled_for, state, title, body, notes, score, now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_content(conn: sqlite3.Connection, brand_id: int, *, limit: int = 100) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM content WHERE brand_id = ?
           ORDER BY CASE state WHEN 'a_valider' THEN 0 WHEN 'valide' THEN 1 WHEN 'publie' THEN 2
                               WHEN 'genere' THEN 3 ELSE 4 END,
                    COALESCE(scheduled_for, created_at) LIMIT ?""",
        (brand_id, limit),
    ).fetchall()


def content_stats(conn: sqlite3.Connection, brand_id: int) -> dict[str, int]:
    rows = conn.execute("SELECT state, COUNT(*) AS n FROM content WHERE brand_id = ? GROUP BY state",
                        (brand_id,)).fetchall()
    return {r["state"]: r["n"] for r in rows}
