"""Audit SEO et GEO d'un site, automatique et gratuit.

Aucun appel à un modèle de langage : chaque constat est une règle vérifiable,
appliquée à ce que le crawler a réellement lu. C'est volontaire. Un audit doit
être reproductible — relancé demain, il dit la même chose si rien n'a changé —
et il doit pouvoir tourner chaque nuit sur cinquante sites sans coûter un euro.
Le modèle intervient après, pour expliquer et proposer des corrections.

Chaque constat dit, en français clair, ce qui ne va pas, pourquoi ça compte,
et quoi faire. Sa gravité est l'un de trois niveaux :

- **critique** : le site perd des visiteurs ou des clients maintenant ;
- **important** : Google ou les IA comprennent mal le site ;
- **amélioration** : un gain réel, mais pas urgent.
"""

from __future__ import annotations

import re
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from typing import Literal
from urllib.parse import urlparse

import httpx2 as httpx

from .crawl import SKIP_PATTERNS, USER_AGENT, Page, _robots, fetch_page

Severity = Literal["critique", "important", "amelioration"]
Category = Literal["technique", "contenu", "geo", "accessibilite"]

SEVERITY_WEIGHT = {"critique": 15, "important": 6, "amelioration": 2}

#: Attente entre deux essais quand une adresse ne répond pas (secondes).
RETRY_DELAY = 1.5

#: Types Schema.org qui aident Google et les IA à comprendre une entreprise.
BUSINESS_TYPES = {
    "Organization", "LocalBusiness", "Corporation", "TravelAgency", "MedicalBusiness",
    "MedicalClinic", "Physician", "Store", "Restaurant", "ProfessionalService",
    "FinancialService", "BankOrCreditUnion", "Hotel", "LodgingBusiness",
}
#: Types qui rendent une réponse directement citable par une IA.
ANSWER_TYPES = {"FAQPage", "HowTo", "QAPage", "MedicalWebPage", "Article", "BlogPosting"}


@dataclass
class Finding:
    code: str
    severity: Severity
    category: Category
    title: str
    why: str
    fix: str
    urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditResult:
    url: str
    pages: list[Page]
    findings: list[Finding]
    score: int

    @property
    def counts(self) -> dict[str, int]:
        c = Counter(f.severity for f in self.findings)
        return {s: c.get(s, 0) for s in ("critique", "important", "amelioration")}


# --------------------------------------------------------------------------- #
# Parcours du site
# --------------------------------------------------------------------------- #

def crawl(start_url: str, *, max_pages: int = 40, client: httpx.Client) -> list[Page]:
    """Parcourt le site en largeur, page par page, dans la limite de `max_pages`.

    Reste sur le même domaine, respecte robots.txt, ignore les fichiers et les
    espaces privés.
    """
    robots = _robots(client, start_url)
    host = urlparse(start_url).netloc
    seen: set[str] = set()
    queue: deque[tuple[str, str]] = deque([(start_url, "accueil")])
    pages: list[Page] = []

    while queue and len(pages) < max_pages:
        url, role = queue.popleft()
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        if not robots.can_fetch(USER_AGENT, url):
            continue
        page = fetch_page(client, url, role)
        # Deux adresses peuvent mener à la même page après redirection
        # (« / » → « /fr »). On la compte une fois, sinon l'audit croit voir
        # deux pages au même titre.
        final = page.url.rstrip("/")
        if final != key and final in seen:
            continue
        seen.add(final)
        pages.append(page)
        for link in page.links:
            if urlparse(link).netloc == host and link.rstrip("/") not in seen and not SKIP_PATTERNS.search(link):
                queue.append((link, "page"))
    return pages


# --------------------------------------------------------------------------- #
# Règles au niveau du site
# --------------------------------------------------------------------------- #

def _status(client: httpx.Client, url: str, *, attempts: int = 3) -> tuple[int, str]:
    """Code HTTP et cible de redirection, sans suivre la redirection.

    Un échec de connexion est réessayé avant de conclure : une coupure passagère
    ne doit jamais devenir un constat « critique » dans un audit qu'on envoie.
    """
    import time

    for attempt in range(attempts):
        try:
            r = client.get(url, follow_redirects=False)
            return r.status_code, r.headers.get("location", "")
        except httpx.HTTPError:
            if attempt < attempts - 1:
                time.sleep(RETRY_DELAY)
    return 0, ""


def site_checks(root_url: str, client: httpx.Client) -> list[Finding]:
    findings: list[Finding] = []
    parsed = urlparse(root_url)
    host = parsed.netloc
    bare = host[4:] if host.startswith("www.") else host
    www = f"www.{bare}"
    base = f"{parsed.scheme}://{host}"

    # 1. Les deux versions du domaine.
    variants = {h: _status(client, f"https://{h}/") for h in (bare, www)}
    dead = [h for h, (code, _) in variants.items() if code == 0]
    if dead and len(dead) < 2:
        findings.append(Finding(
            "domaine-injoignable", "critique", "technique",
            f"« {dead[0]} » ne répond pas",
            "Une partie des visiteurs tape l'adresse sans (ou avec) « www ». "
            "Chez eux, le site ne s'affiche pas : ils pensent qu'il est en panne et repartent. "
            "Constaté depuis notre serveur d'audit : à confirmer en tapant l'adresse dans un navigateur.",
            f"Faire pointer « {dead[0]} » vers le site et le rediriger (301) vers la version principale. "
            "C'est un réglage DNS chez l'hébergeur, quelques minutes.",
            [f"https://{dead[0]}/"],
        ))
    live = {h: v for h, v in variants.items() if v[0] not in (0,)}
    if len(live) == 2:
        redirects = [h for h, (code, loc) in live.items()
                     if code in (301, 308) and urlparse(loc).netloc not in ("", h)]
        if not redirects:
            findings.append(Finding(
                "domaine-duplique", "important", "technique",
                "Le site répond avec et sans « www », sans rediriger l'un vers l'autre",
                "Google voit deux sites identiques et partage sa confiance entre les deux "
                "au lieu de la concentrer sur un seul.",
                "Choisir une version et rediriger l'autre en 301 (permanente).",
                [f"https://{h}/" for h in live],
            ))

    # 2. http → https.
    code, location = _status(client, f"http://{host}/")
    if code == 200:
        findings.append(Finding(
            "http-sans-redirection", "important", "technique",
            "Le site est accessible en « http » non sécurisé",
            "Les navigateurs affichent « Non sécurisé » et Google privilégie la version sécurisée.",
            "Rediriger toute adresse http:// vers https:// en 301.",
            [f"http://{host}/"],
        ))

    # 3. robots.txt, sitemap.xml, llms.txt
    robots_code, _ = _status(client, f"{base}/robots.txt")
    if robots_code != 200:
        findings.append(Finding(
            "robots-absent", "amelioration", "technique",
            "Pas de fichier robots.txt",
            "Ce fichier indique aux moteurs ce qu'ils peuvent explorer et où trouver le plan du site.",
            "Créer /robots.txt avec au minimum l'adresse du sitemap.",
            [f"{base}/robots.txt"],
        ))
    sitemap_code, _ = _status(client, f"{base}/sitemap.xml")
    if sitemap_code not in (200, 301, 302, 307, 308):
        findings.append(Finding(
            "sitemap-absent", "important", "technique",
            "Pas de plan du site (sitemap.xml)",
            "Sans plan, Google découvre les pages au hasard des liens : certaines ne sont jamais indexées.",
            "Générer /sitemap.xml avec toutes les pages publiques, puis le déclarer dans Google Search Console.",
            [f"{base}/sitemap.xml"],
        ))
    llms_code, _ = _status(client, f"{base}/llms.txt")
    if llms_code != 200:
        findings.append(Finding(
            "llms-absent", "amelioration", "geo",
            "Pas de fichier llms.txt pour les IA",
            "Ce fichier résume l'entreprise pour ChatGPT, Claude ou Perplexity, qui s'en servent "
            "pour décider qui citer. C'est récent, et les concurrents l'ont rarement.",
            "Créer /llms.txt : qui vous êtes, ce que vous vendez, les pages clés, les informations vérifiables.",
            [f"{base}/llms.txt"],
        ))
    return findings


# --------------------------------------------------------------------------- #
# Règles page par page
# --------------------------------------------------------------------------- #

PLACEHOLDER = re.compile(
    r"^(choisir|engagement|test|page|sample|exemple|brouillon|untitled|sans titre|lorem)\b[\s\-]*\d*\s*([–|-].*)?$",
    re.I,
)


def page_checks(pages: list[Page]) -> list[Finding]:
    readable = [p for p in pages if not p.error and p.seo is not None]
    # Une page brouillon a un seul vrai problème : être en ligne. La signaler
    # aussi pour son titre ou sa meta gonflerait l'audit de bruit.
    drafts = [p.url for p in readable if p.seo.title and PLACEHOLDER.match(p.seo.title.strip())]
    ok = [p for p in readable if p.url not in drafts]
    findings: list[Finding] = []

    def add(code, severity, category, title, why, fix, urls):
        if urls:
            findings.append(Finding(code, severity, category, title, why, fix, sorted(set(urls))))

    broken = [p.url for p in pages if p.error and p.status >= 400]
    add("pages-cassees", "critique", "technique",
        f"{len(broken)} page(s) en erreur",
        "Un lien qui mène à une erreur fait fuir le visiteur et gaspille l'exploration de Google.",
        "Corriger ou rediriger ces adresses vers la page la plus proche.", broken)

    add("title-absent", "critique", "contenu", "Pages sans titre",
        "Le titre est la ligne bleue cliquable dans Google. Sans lui, Google en invente un.",
        "Écrire un titre unique par page, 30 à 60 caractères, avec ce que cherche le client.",
        [p.url for p in ok if not p.seo.title])
    add("title-court", "important", "contenu", "Titres trop courts",
        "Un titre comme « Contact » ou « Qui sommes-nous » ne dit ni qui vous êtes, ni ce que vous faites.",
        "Ajouter l'activité et la marque : « Contact — [ce que vous vendez] | [votre marque] ».",
        [p.url for p in ok if p.seo.title and p.seo.title_length < 25])
    add("title-long", "amelioration", "contenu", "Titres trop longs",
        "Au-delà d'environ 60 caractères, Google coupe le titre au milieu.",
        "Raccourcir en gardant l'essentiel au début.",
        [p.url for p in ok if p.seo.title_length > 65])
    dup_titles = [t for t, n in Counter(p.seo.title for p in ok if p.seo.title).items() if n > 1]
    add("title-duplique", "important", "contenu", "Plusieurs pages ont le même titre",
        "Google ne sait pas laquelle montrer, et elles se font concurrence entre elles.",
        "Donner à chaque page un titre qui la distingue.",
        [p.url for p in ok if p.seo.title in dup_titles])

    add("meta-absente", "important", "contenu", "Pages sans meta description",
        "C'est le texte gris sous le titre dans Google : votre argument pour obtenir le clic.",
        "Écrire 120 à 155 caractères par page, avec un bénéfice concret et un appel à l'action.",
        [p.url for p in ok if not p.seo.meta_description])
    dup_meta = [m for m, n in Counter(p.seo.meta_description for p in ok if p.seo.meta_description).items() if n > 1]
    add("meta-dupliquee", "amelioration", "contenu", "Meta descriptions identiques sur plusieurs pages",
        "Google les ignore souvent et écrit les siennes, moins vendeuses.",
        "Une description propre à chaque page.",
        [p.url for p in ok if p.seo.meta_description in dup_meta])

    add("h1-absent", "important", "contenu", "Pages sans titre principal (H1)",
        "Le H1 dit à Google et aux lecteurs de quoi parle la page.",
        "Un H1 par page, qui reprend l'intention de recherche.",
        [p.url for p in ok if not p.seo.h1])
    add("h1-multiple", "amelioration", "contenu", "Plusieurs H1 sur une même page",
        "Le sujet principal devient flou pour les moteurs.",
        "Garder un seul H1 et passer les autres en H2.",
        [p.url for p in ok if len(p.seo.h1) > 1])
    add("h1-casse", "important", "contenu", "Titre principal mal formé",
        "Un H1 qui commence par des symboles parasites (« | | … ») est mal lu par Google "
        "et fait amateur aux yeux d'une IA qui le cite.",
        "Nettoyer le H1 : supprimer les séparateurs ou éléments vides du modèle de page.",
        [p.url for p in ok if any(h.strip().startswith(("|", "-", "•")) or h.count("|") >= 2 for h in p.seo.h1)])

    add("contenu-mince", "amelioration", "contenu", "Pages avec très peu de texte",
        "Moins de 150 mots, c'est trop peu pour que Google ou une IA comprenne et recommande la page.",
        "Développer : à qui s'adresse l'offre, ce qu'elle comprend, le prix, les questions fréquentes.",
        [p.url for p in ok if p.seo.word_count < 150 and not p.seo.noindex])

    add("canonical-absente", "amelioration", "technique", "Pas d'adresse canonique déclarée",
        "La canonique dit à Google quelle adresse est la bonne quand une page en a plusieurs.",
        "Ajouter <link rel=\"canonical\"> sur chaque page.",
        [p.url for p in ok if not p.seo.canonical])
    add("noindex", "critique", "technique", "Pages exclues de Google (noindex)",
        "Ces pages sont explicitement interdites d'indexation. Si c'est involontaire, elles sont invisibles.",
        "Vérifier une par une ; retirer « noindex » sur toute page qui doit être trouvée.",
        [p.url for p in ok if p.seo.noindex])
    add("lang-absente", "amelioration", "technique", "Langue de la page non déclarée",
        "Les moteurs et les lecteurs d'écran devinent la langue, parfois mal.",
        "Ajouter lang=\"fr\" sur la balise <html>.",
        [p.url for p in ok if not p.seo.lang])
    add("viewport-absent", "important", "technique", "Page non adaptée au mobile",
        "Sans réglage d'affichage mobile, la page s'affiche en miniature sur téléphone.",
        "Ajouter <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.",
        [p.url for p in ok if not p.seo.has_viewport])
    add("og-absent", "amelioration", "contenu", "Pas d'aperçu prévu pour les partages",
        "Partagée sur WhatsApp, Facebook ou LinkedIn, la page s'affiche sans image ni titre propre.",
        "Ajouter les balises Open Graph (og:title, og:description, og:image).",
        [p.url for p in ok if not p.seo.og_tags])
    add("images-sans-alt", "amelioration", "accessibilite", "Images sans texte alternatif",
        "Google Images ne sait pas ce qu'elles montrent, et les lecteurs d'écran non plus.",
        "Décrire chaque image utile en quelques mots (attribut alt).",
        [p.url for p in ok if p.seo.images_missing_alt > 0])

    # Restes de chantier, fréquents sous WordPress
    add("page-brouillon", "critique", "contenu", "Des pages brouillon sont en ligne",
        "Des pages de travail (« choisir 1 », « test »…) sont publiques et indexables. Un prospect "
        "ou une IA qui tombe dessus en conclut que le site n'est pas tenu.",
        "Les dépublier, ou les passer en « noindex » si elles servent à quelque chose.",
        drafts)
    add("page-doublon", "important", "technique", "Pages publiées en plusieurs exemplaires",
        "Une adresse finissant par « -2 » ou « -3 » signale presque toujours une page dupliquée : "
        "plusieurs versions coexistent et se font concurrence dans Google.",
        "Garder la bonne version, rediriger (301) les autres vers elle, et renommer l'adresse sans suffixe.",
        # Une page brouillon est déjà signalée : on ne la compte pas deux fois.
        [p.url for p in ok if re.search(r"-[2-9]/?$", urlparse(p.url).path)])

    # GEO : être compris et cité par les IA
    all_types = {t for p in ok for t in p.seo.jsonld_types}
    if ok and not all_types:
        add("jsonld-absent", "important", "geo", "Aucune donnée structurée sur le site",
            "Les données structurées disent aux machines, sans ambiguïté : qui vous êtes, ce que vous "
            "vendez, à quel prix, où. Sans elles, Google et les IA déduisent — et se trompent.",
            "Ajouter au minimum un bloc Organization (ou le type de votre activité) sur l'accueil, "
            "et FAQPage sur les pages qui répondent à des questions.",
            [ok[0].url])
    elif ok and not (all_types & BUSINESS_TYPES):
        add("jsonld-entreprise", "important", "geo", "L'entreprise n'est pas décrite pour les machines",
            "Des données structurées existent, mais aucune ne dit qui vous êtes : nom, activité, contact.",
            "Ajouter un bloc Organization ou le type précis de l'activité sur l'accueil.", [ok[0].url])
    if ok and all_types and not (all_types & ANSWER_TYPES):
        add("geo-pas-de-reponses", "amelioration", "geo", "Aucune page de réponses structurées",
            "Les IA citent volontiers une réponse claire à une question précise. Une FAQ balisée "
            "est l'un des formats qu'elles reprennent le plus facilement.",
            "Ajouter une FAQ balisée (FAQPage) sur les pages d'offre.", [ok[0].url])
    add("jsonld-invalide", "important", "geo", "Données structurées illisibles",
        "Un bloc mal formé est ignoré en entier par Google.",
        "Corriger le JSON (le tester dans l'outil de test des résultats enrichis de Google).",
        [p.url for p in ok if "JSON-LD invalide" in p.seo.jsonld_types])
    return findings


# --------------------------------------------------------------------------- #
# Lancement
# --------------------------------------------------------------------------- #

def score(findings: list[Finding]) -> int:
    """Note sur 100. Chaque constat pèse selon sa gravité, multiplié — avec un
    plafond — par le nombre de pages touchées.

    La pénalité est amortie plutôt que soustraite : au-delà d'une dizaine de
    constats, une soustraction donne 0 à tous les sites, qui ne se distinguent
    plus entre eux ; et un « 0/100 » dans un audit envoyé ressemble à une
    provocation, pas à un diagnostic.
    """
    import math

    penalty = sum(SEVERITY_WEIGHT[f.severity] * min(1 + len(f.urls) / 10, 2) for f in findings)
    return round(100 * math.exp(-penalty / 80))


def _variants(url: str) -> list[str]:
    """L'adresse donnée d'abord, puis l'autre version du domaine."""
    parsed = urlparse(url)
    host = parsed.netloc
    other = host[4:] if host.startswith("www.") else f"www.{host}"
    path = parsed.path or "/"
    return [url, f"https://{other}{path}"]


def run(url: str, *, max_pages: int = 40, client: httpx.Client | None = None) -> AuditResult:
    if not urlparse(url).scheme:
        url = f"https://{url}"
    own = client is None
    client = client or httpx.Client(timeout=20.0, follow_redirects=True,
                                    headers={"User-Agent": USER_AGENT,
                                             "Accept-Language": "fr-FR,fr;q=0.9"})
    try:
        pages: list[Page] = []
        for candidate in _variants(url):
            pages = crawl(candidate, max_pages=max_pages, client=client)
            if pages and not pages[0].error:
                break
        if not pages or pages[0].error:
            # Aucune version du site n'a répondu. On ne vérifie rien d'autre :
            # des constats tirés d'une adresse morte seraient faux, et un audit
            # faux envoyé à un prospect coûte plus cher que pas d'audit.
            detail = pages[0].error if pages else "aucune réponse"
            return AuditResult(url=url, pages=pages, score=0, findings=[Finding(
                "site-illisible", "critique", "technique", "Le site n'a pas pu être lu",
                f"Aucune version du site n'a répondu à l'audit ({detail}).",
                "Vérifier l'adresse et relancer. Si le site s'ouvre dans un navigateur, il bloque "
                "peut-être les robots : l'audit ne peut alors rien conclure.",
                [url])])
        root = pages[0].url
        findings = site_checks(root, client) + page_checks(pages)
    finally:
        if own:
            client.close()
    order = {"critique": 0, "important": 1, "amelioration": 2}
    findings.sort(key=lambda f: (order[f.severity], -len(f.urls)))
    return AuditResult(url=url, pages=pages, findings=findings, score=score(findings))
