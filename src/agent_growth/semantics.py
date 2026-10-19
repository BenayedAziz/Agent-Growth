"""Sémantique : sur quels mots-clés le site existe, et sur lesquels il est absent.

Trois sources, aucune à abonnement :

1. **Le site lui-même** (automatique) : les termes que chaque page met en avant
   — titre, H1, expressions qui reviennent dans le texte. C'est ce que Google
   comprend du site.
2. **Les mots-clés des clients** (`mots-cles.json`, rempli par le consultant) :
   ce que tape un client qui ne connaît pas la marque, trouvé en cherchant sur
   Google à la main (suggestions, « Autres questions posées ») et, si on a un
   compte Google Ads, dans Keyword Planner pour les volumes. On y note la
   position observée dans Google. L'outil dit ensuite quelle page cible chaque
   mot-clé — ou qu'aucune ne le fait.
3. **Google Search Console** (si le client nous donne l'accès) : les vraies
   recherches sur lesquelles le site apparaît, avec impressions et position.
   Export CSV « Performances → Exporter », lu tel quel.

Aucun volume de recherche n'est inventé : sans Keyword Planner ni Search
Console, la colonne reste vide et le rapport le dit.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

STOPWORDS = frozenset("""
a au aux avec ce ces cet cette d da dans de des du elle en et eux il ils je la le les leur leurs lui
ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu que qui sa se ses son sur ta te
tes toi ton tu un une vos votre vous y l s n c j m t est sont etre avoir plus tout tous toute toutes
comme sans chez entre vers fait faire peut aussi bien tres ici ainsi dont the and of to for in on
with your our you
""".split())


def normalize(text: str) -> str:
    """Minuscules, sans accents ni ponctuation : « Crédit Immobilier » → « credit immobilier »."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _stem(word: str) -> str:
    """Pluriel français grossier : « credits » et « credit » se rejoignent."""
    return word[:-1] if len(word) > 3 and word[-1] in "sx" else word


def tokens(text: str) -> list[str]:
    return [_stem(w) for w in normalize(text).split() if w not in STOPWORDS and len(w) > 1]


def _near(haystack: list[str], needle: list[str], window: int = 10) -> bool:
    """Tous les mots du mot-clé à quelques mots d'écart : « rhinoplastie… au
    Maroc » parle bien de « rhinoplastie maroc », pas une page qui dit
    « rhinoplastie » en haut et « Maroc » en bas."""
    wanted = set(needle)
    if not wanted:
        return False
    return any(word in wanted and wanted <= set(haystack[i:i + window])
               for i, word in enumerate(haystack))


# --------------------------------------------------------------------------- #
# Ce que dit chaque page
# --------------------------------------------------------------------------- #

def page_index(pages) -> list[dict]:
    """Le strict nécessaire pour l'analyse, gardé dans `audit.json` : on peut
    ainsi refaire la sémantique avec une nouvelle liste de mots-clés sans
    relire le site."""
    out = []
    for p in pages:
        if p.error or p.seo is None:
            continue
        out.append({"url": p.url, "title": p.seo.title, "h1": p.seo.h1[:3], "h2": p.seo.h2[:15],
                    "text": p.text[:20000]})
    return out


def _words(text: str) -> list[tuple[str, int, int]]:
    """(forme comparable, début, fin) de chaque mot utile du texte : la
    position permet de réafficher l'expression telle qu'elle est écrite."""
    out = []
    for match in re.finditer(r"[^\W_]+", text):
        norm = normalize(match.group())
        if norm and norm not in STOPWORDS and len(norm) > 1 and not norm.isdigit():
            out.append((_stem(norm), match.start(), match.end()))
    return out


BREAK = re.compile(r"[.!?;:|•·\n()\[\]«»\"/]")


def _grams(text: str) -> tuple[Counter[str], dict[str, Counter[str]]]:
    """Expressions de 2 et 3 mots, sans enjamber une ponctuation."""
    words = _words(text)
    counts: Counter[str] = Counter()
    surface: dict[str, Counter[str]] = {}
    for n in (2, 3):
        for i in range(len(words) - n + 1):
            chunk = words[i:i + n]
            if BREAK.search(text[chunk[0][2]:chunk[-1][1]]):
                continue
            key = " ".join(w for w, _, _ in chunk)
            counts[key] += 1
            written = re.sub(r"\s+", " ", text[chunk[0][1]:chunk[-1][2]]).lower()
            surface.setdefault(key, Counter())[written] += 1
    return counts, surface


def footprint(index: list[dict], top: int = 5) -> list[dict]:
    """Pour chaque page : son expression principale et les expressions qui
    reviennent le plus dans son texte (au moins trois fois), écrites comme sur
    le site.

    Ce qui se répète sur plus de la moitié des pages (menu, bouton « demander
    un devis », pied de page) est écarté : ça ne dit rien du sujet de la page."""
    grams = [_grams(page["text"]) for page in index]
    spread: Counter[str] = Counter(key for counts, _ in grams for key in counts)
    boilerplate = {k for k, n in spread.items() if len(index) >= 4 and n > len(index) / 2}
    rows = []
    for page, (counts, surface) in zip(index, grams, strict=True):
        best: list[str] = []
        for key, count in counts.most_common(80):
            if count < 3:
                break
            if key in boilerplate:
                continue
            # Pas de doublon partiel : « crédit immobilier » suffit si
            # « crédit immobilier tunisie » est déjà retenu, et inversement.
            if not any(key in kept or kept in key for kept in best):
                best.append(key)
            if len(best) == top:
                break
        main = page["h1"][0] if page["h1"] else page["title"]
        rows.append({"url": page["url"], "main": main, "title": page["title"],
                     "terms": [surface[k].most_common(1)[0][0] for k in best]})
    return rows


# --------------------------------------------------------------------------- #
# Mots-clés des clients
# --------------------------------------------------------------------------- #

def keyword_template() -> list[dict]:
    return [{"mot_cle": "", "position": None, "volume": None, "valide": True, "note": ""}]


def coverage(keywords: list[dict], index: list[dict]) -> list[dict]:
    """Pour chaque mot-clé : la page qui le cible le mieux et son statut.

    - **ciblé** : il est dans le titre ou le H1 d'une page — Google sait quelle
      page montrer ;
    - **mentionné** : ses mots apparaissent ensemble dans un texte, mais aucune
      page n'en fait son sujet ;
    - **absent** : le site n'en parle pas.
    """
    rows = []
    for kw in keywords:
        phrase = kw.get("mot_cle", "").strip()
        need = tokens(phrase)
        if not need:
            continue
        scored = []
        for page in index:
            title, h1 = set(tokens(page["title"])), set(tokens(" ".join(page["h1"])))
            path = set(tokens(unquote(urlparse(page["url"]).path)))
            points = (3 if set(need) <= title else 0) + (3 if set(need) <= h1 else 0) \
                + (2 if set(need) <= path else 0)
            mentioned = _near(tokens(" ".join([*page["h2"], page["text"]])), need)
            if points or mentioned:
                scored.append((points, mentioned, page["url"]))
        scored.sort(key=lambda s: (-s[0], not s[1]))
        targeted = [url for points, _, url in scored if points >= 3]
        status = "cible" if targeted else "mentionne" if scored else "absent"
        rows.append({
            "keyword": phrase, "status": status,
            "page": scored[0][2] if scored else "",
            "competing": targeted[1:] if len(targeted) > 1 else [],
            "position": kw.get("position"), "volume": kw.get("volume"),
            "valide": kw.get("valide", True), "note": kw.get("note", ""),
            "source": "",
        })
    return rows


# --------------------------------------------------------------------------- #
# Google Search Console
# --------------------------------------------------------------------------- #

QUERY_COLUMNS = ("Requêtes les plus fréquentes", "Top queries", "Requête", "Query")
COLUMNS = {
    "clicks": ("Clics", "Clicks"),
    "impressions": ("Impressions",),
    "ctr": ("CTR",),
    "position": ("Position",),
}


def _number(value: str) -> float:
    value = (value or "").replace(" ", "").replace(" ", "").replace("%", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return 0.0


def load_search_console(path: str | Path) -> list[dict]:
    """Export « Performances » de Search Console : le zip tel quel, ou le
    fichier des requêtes qu'il contient."""
    path = Path(path)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            name = next((n for n in archive.namelist()
                         if normalize(Path(n).stem) in ("requetes", "queries")), None)
            if name is None:
                raise ValueError("Le zip Search Console ne contient pas de fichier « Requêtes » / « Queries ».")
            text = archive.read(name).decode("utf-8-sig")
    else:
        text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    query_col = next((c for c in QUERY_COLUMNS if c in fields), None)
    if query_col is None:
        raise ValueError("Export Search Console non reconnu : pas de colonne « Requêtes les plus fréquentes » "
                         "ni « Top queries ». Exporter l'onglet Requêtes de « Performances ».")
    cols = {key: next((c for c in names if c in fields), None) for key, names in COLUMNS.items()}
    rows = []
    for row in reader:
        rows.append({"query": row[query_col],
                     **{key: _number(row[col]) if col else 0.0 for key, col in cols.items()}})
    rows.sort(key=lambda r: (-r["clicks"], -r["impressions"]))
    return rows


def enrich(rows: list[dict], *, queries: list[dict] | None = None, market: dict | None = None) -> list[dict]:
    """Complète les mots-clés du consultant avec les données de Google.

    Position : la Search Console d'abord (trois mois de vraies recherches),
    puis DataForSEO, puis la position relevée à la main. Volume et difficulté :
    DataForSEO, sinon ce que le consultant a noté (Keyword Planner)."""
    by_query = {" ".join(tokens(q["query"])): q for q in queries or []}
    market = market or {}
    ranked = {" ".join(tokens(r["keyword"])): r for r in market.get("ranked", [])}
    overview = {" ".join(tokens(k)): v for k, v in (market.get("overview") or {}).items()}
    for row in rows:
        key = " ".join(tokens(row["keyword"]))
        if key in by_query:
            q = by_query[key]
            row.update(position=round(q["position"], 1), impressions=int(q["impressions"]),
                       clicks=int(q["clicks"]), source="search-console")
        elif key in ranked:
            row.update(position=ranked[key]["position"], source="dataforseo")
        elif market:
            row.update(position=None, source="dataforseo")
        elif row.get("position") is not None:
            row["source"] = "recherche manuelle"
        if key in overview:
            row.update(volume=overview[key]["volume"], difficulty=overview[key]["difficulty"])
    return rows


def near_first_page(queries: list[dict], ranked: list[dict] | None = None, minimum: int = 20) -> list[str]:
    """Recherches où le site est en page 2 (positions 8 à 20) mais déjà vu :
    le gain le plus rapide du référencement. Search Console si on l'a (seuil
    en affichages), sinon DataForSEO (seuil en recherches mensuelles)."""
    if queries:
        return [q["query"] for q in queries if 8 <= q["position"] <= 20 and q["impressions"] >= minimum]
    return [r["keyword"] for r in ranked or []
            if r["position"] and 8 <= r["position"] <= 20 and (r["volume"] or 0) >= minimum]
