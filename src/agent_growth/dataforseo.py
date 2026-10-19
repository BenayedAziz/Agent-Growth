"""Données de mots-clés : volumes, positions, concurrents — via DataForSEO.

Semrush et Ahrefs revendent sous abonnement des données que DataForSEO vend à
l'unité : volumes de recherche (Google Ads), positions dans Google, domaines
concurrents. C'est la source du projet open-source OpenSEO
(github.com/every-app/open-seo, licence MIT), dont ce module reprend les choix
d'appels et de paramètres — voir THIRD_PARTY_NOTICES.md. On n'en reprend pas
l'interface : la nôtre est faite pour un dirigeant, pas pour un expert SEO.

Pourquoi pas « scraper » Google nous-mêmes : Google bloque un serveur qui
l'interroge en série, ses conditions l'interdisent, et les volumes de
recherche n'apparaissent de toute façon dans aucune page Google. DataForSEO
fait cette collecte à grande échelle ; on paie à la requête.

Coût (tarifs relevés par OpenSEO, septembre 2026) : 0,012 $ par requête et
0,00012 $ par ligne renvoyée. Un audit complet — mots-clés du site, trois
concurrents, écart, volumes de la liste du consultant — coûte environ 0,20 $.
Chaque appel renvoie son coût réel, additionné dans `cost_usd`.

Clé : `DATAFORSEO_API_KEY`, la valeur « Base64 » donnée par DataForSEO
(identifiant:mot de passe encodés). Variable d'environnement uniquement.
"""

from __future__ import annotations

import os
from datetime import date
from urllib.parse import urlparse

import httpx2 as httpx

from .semantics import tokens

API = "https://api.dataforseo.com"
TIMEOUT = 60.0

#: Marché → (code de lieu Google Ads, langue). Le code d'un pays est 2000 + son
#: code ISO numérique.
MARKETS: dict[str, tuple[int, str]] = {
    "fr": (2250, "fr"), "be": (2056, "fr"), "ch": (2756, "fr"), "ca": (2124, "fr"),
    "ma": (2504, "fr"), "tn": (2788, "fr"), "us": (2840, "en"), "uk": (2826, "en"),
}

#: Domaines qui sortent partout et ne sont les concurrents de personne.
NOT_COMPETITORS = (
    "wikipedia.org", "youtube.com", "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
    "x.com", "tiktok.com", "pinterest.", "reddit.com", "amazon.", "google.", "pagesjaunes.fr",
    "doctissimo.fr", "quora.com", "tripadvisor.",
)


class DataForSEOError(RuntimeError):
    pass


def available() -> bool:
    return bool(os.environ.get("DATAFORSEO_API_KEY"))


def _domain(url: str) -> str:
    host = urlparse(url if "//" in url else f"https://{url}").netloc or url
    return host.lower().removeprefix("www.")


class Client:
    def __init__(self, api_key: str | None = None, *, http: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("DATAFORSEO_API_KEY", "")
        if not self.api_key:
            raise DataForSEOError(
                "Clé DataForSEO absente : créer un compte sur dataforseo.com, copier les identifiants "
                "« Base64 » et les mettre dans la variable DATAFORSEO_API_KEY."
            )
        self.http = http or httpx.Client(timeout=TIMEOUT)
        self.cost_usd = 0.0

    def post(self, path: str, task: dict) -> dict:
        """Un appel « live ». Renvoie le premier résultat de la tâche."""
        try:
            r = self.http.post(f"{API}{path}", json=[task],
                               headers={"Authorization": f"Basic {self.api_key}"})
        except httpx.HTTPError as exc:
            raise DataForSEOError(f"DataForSEO injoignable ({type(exc).__name__})") from exc
        if r.status_code == 401:
            raise DataForSEOError("DataForSEO refuse la clé (401) : vérifier DATAFORSEO_API_KEY.")
        if r.status_code == 402:
            raise DataForSEOError("Crédit DataForSEO épuisé (402) : recharger le compte.")
        if r.status_code != 200:
            raise DataForSEOError(f"DataForSEO a répondu {r.status_code}.")
        body = r.json()
        tasks = body.get("tasks") or [{}]
        task_out = tasks[0]
        self.cost_usd += float(task_out.get("cost") or 0)
        if body.get("status_code") != 20000 or task_out.get("status_code") != 20000:
            message = task_out.get("status_message") or body.get("status_message") or "erreur inconnue"
            raise DataForSEOError(f"DataForSEO : {message}")
        return (task_out.get("result") or [{}])[0] or {}

    # ----------------------------------------------------------------- #
    # Les quatre appels dont l'audit a besoin
    # ----------------------------------------------------------------- #

    def ranked_keywords(self, target: str, market: str = "fr", *, limit: int = 200,
                        max_position: int = 100) -> list[dict]:
        """Les recherches sur lesquelles le domaine sort dans Google, les plus
        cherchées d'abord."""
        location, language = MARKETS[market]
        result = self.post("/v3/dataforseo_labs/google/ranked_keywords/live", {
            "target": _domain(target), "location_code": location, "language_code": language,
            "limit": limit, "item_types": ["organic"],
            "order_by": ["keyword_data.keyword_info.search_volume,desc"],
            "filters": [["ranked_serp_element.serp_item.rank_group", "<=", max_position]],
        })
        rows = []
        for item in result.get("items") or []:
            data = item.get("keyword_data") or {}
            serp = (item.get("ranked_serp_element") or {}).get("serp_item") or {}
            info = data.get("keyword_info") or {}
            rows.append({
                "keyword": data.get("keyword") or item.get("keyword") or "",
                "position": serp.get("rank_group") or serp.get("rank_absolute"),
                "volume": info.get("search_volume"),
                "difficulty": (data.get("keyword_properties") or {}).get("keyword_difficulty"),
                "url": serp.get("url") or "",
                "traffic": round(serp.get("etv") or 0, 1),
            })
        return [r for r in rows if r["keyword"]]

    def serp_competitors(self, keywords: list[str], market: str = "fr", *, limit: int = 20) -> list[dict]:
        """Les domaines qui sortent le plus sur ces recherches."""
        location, language = MARKETS[market]
        result = self.post("/v3/dataforseo_labs/google/serp_competitors/live", {
            "keywords": keywords[:200], "location_code": location, "language_code": language,
            "item_types": ["organic"], "limit": limit,
        })
        return [{"domain": i.get("domain", ""), "avg_position": i.get("avg_position"),
                 "keywords": i.get("keywords_count"), "visibility": i.get("visibility")}
                for i in result.get("items") or [] if i.get("domain")]

    def keyword_overview(self, keywords: list[str], market: str = "fr") -> dict[str, dict]:
        """Volume mensuel, difficulté et intention de chaque mot-clé."""
        if not keywords:
            return {}
        location, language = MARKETS[market]
        result = self.post("/v3/dataforseo_labs/google/keyword_overview/live", {
            "keywords": keywords[:700], "location_code": location, "language_code": language,
        })
        out = {}
        for item in result.get("items") or []:
            info = item.get("keyword_info") or {}
            out[item.get("keyword", "")] = {
                "volume": info.get("search_volume"),
                "difficulty": (item.get("keyword_properties") or {}).get("keyword_difficulty"),
                "intent": (item.get("search_intent_info") or {}).get("main_intent"),
                "cpc": info.get("cpc"),
            }
        return out

    def keyword_suggestions(self, seed: str, market: str = "fr", *, limit: int = 50) -> list[dict]:
        """Recherches qui contiennent `seed`, les plus cherchées d'abord."""
        location, language = MARKETS[market]
        result = self.post("/v3/dataforseo_labs/google/keyword_suggestions/live", {
            "keyword": seed, "location_code": location, "language_code": language, "limit": limit,
            "include_seed_keyword": True, "order_by": ["keyword_info.search_volume,desc"],
        })
        return [{"keyword": i.get("keyword", ""), "volume": (i.get("keyword_info") or {}).get("search_volume")}
                for i in result.get("items") or [] if i.get("keyword")]


def _key(keyword: str) -> str:
    return " ".join(tokens(keyword))


def analyse(url: str, keywords: list[str], *, market: str = "fr", competitors: list[str] | None = None,
            client: Client | None = None, max_competitors: int = 3) -> dict:
    """Toute la sémantique d'un audit, prête à être enregistrée.

    1. les mots-clés sur lesquels le site sort ;
    2. ses concurrents sur Google (donnés, ou trouvés sur ses mots-clés) ;
    3. l'écart : les recherches où un concurrent sort dans les 20 premiers et
       pas le site ;
    4. volume et difficulté de la liste du consultant.
    """
    client = client or Client()
    domain = _domain(url)
    ranked = client.ranked_keywords(domain, market)

    found: list[dict] = []
    if competitors:
        found = [{"domain": _domain(c), "avg_position": None, "keywords": None, "visibility": None}
                 for c in competitors]
    else:
        seeds = [r["keyword"] for r in ranked[:40]] + keywords
        if seeds:
            found = [c for c in client.serp_competitors(list(dict.fromkeys(seeds)), market)
                     if _domain(c["domain"]) != domain
                     and not any(bad in c["domain"] for bad in NOT_COMPETITORS)]
    found = found[:max_competitors]

    ours = {_key(r["keyword"]) for r in ranked}
    gap: dict[str, dict] = {}
    for competitor in found:
        for row in client.ranked_keywords(competitor["domain"], market, limit=200, max_position=20):
            key = _key(row["keyword"])
            if key in ours or not key:
                continue
            best = gap.get(key)
            if best is None or (row["position"] or 99) < (best["position"] or 99):
                gap[key] = {"keyword": row["keyword"], "volume": row["volume"],
                            "competitor": competitor["domain"], "position": row["position"]}
    overview = client.keyword_overview(keywords, market) if keywords else {}

    return {
        "market": market, "fetched_at": date.today().isoformat(), "source": "dataforseo",
        "ranked": ranked, "competitors": found,
        "gap": sorted(gap.values(), key=lambda g: -(g["volume"] or 0))[:50],
        "overview": overview, "cost_usd": round(client.cost_usd, 4),
    }
