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

#: Canaux qui dépensent de l'argent : ils imposent un plafond et une validation.
PAID_CHANNELS = frozenset({"google_ads", "meta_ads"})

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
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
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
    write_access: str = "aucun",
) -> int:
    cur = conn.execute(
        """INSERT OR IGNORE INTO site (brand_id, url, platform, page_count, write_access)
           VALUES (?, ?, ?, ?, ?)""",
        (brand_id, url, platform, page_count, write_access),
    )
    conn.commit()
    return int(cur.lastrowid)


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
                "totals": totals(conn, brand["id"], days=days),
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


def connect_integration(conn: sqlite3.Connection, slug: str, *, secret_ref: str) -> None:
    """Marque un outil comme connecté. `secret_ref` est un nom de variable
    d'environnement ou une clé de coffre — **jamais** le secret."""
    if secret_ref.strip().startswith(("sk-", "key-")) or len(secret_ref) > 80:
        raise ValueError(
            "secret_ref ressemble à un secret. Donne un nom de référence "
            "(ex. « BREVO_API_KEY »), pas la valeur."
        )
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
