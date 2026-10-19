"""Audit SEO et GEO d'un site, automatique et gratuit.

Aucun appel à un modèle de langage : chaque constat est une règle vérifiable,
appliquée à ce que le crawler a réellement lu. C'est volontaire. Un audit doit
être reproductible — relancé demain, il dit la même chose si rien n'a changé —
et il doit pouvoir tourner chaque nuit sur cinquante sites sans coûter un euro.
Le modèle intervient après, pour expliquer et proposer des corrections.

L'audit est rangé en trois piliers, dans l'ordre où Google travaille :

- **Technique** : Google peut-il lire, comprendre et indexer le site ?
- **On-Page** : chaque page dit-elle clairement de quoi elle parle ?
- **E-E-A-T** : le site inspire-t-il confiance — à Google comme au client ?

Trois sources, et seulement trois : notre crawl complet (ou l'export de
Screaming Frog), Google PageSpeed Insights, et une recherche Google faite à la
main par le consultant. Pas d'outil à abonnement.

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
from datetime import date
from typing import Literal
from urllib.parse import quote_plus, urlparse

import httpx2 as httpx

from . import pagespeed
from .crawl import SKIP_PATTERNS, USER_AGENT, Page, _rank_links, _robots, fetch_page

Severity = Literal["critique", "important", "amelioration"]
Category = Literal["technique", "contenu", "geo", "accessibilite"]
Pillar = Literal["technique", "on-page", "eeat"]

PILLARS: dict[str, dict[str, str]] = {
    "technique": {
        "label": "Technique",
        "subtitle": "Ce qui permet à Google de lire, comprendre et indexer le site",
        "intro": "Avant de juger une page, Google doit pouvoir l'atteindre, la charger vite et "
                 "savoir s'il a le droit de la montrer. Un défaut ici rend invisible tout le reste.",
    },
    "on-page": {
        "label": "On-Page",
        "subtitle": "Ce qui signale à Google de quoi parle chaque page",
        "intro": "Titre, description, titre principal, texte : c'est ce que Google lit pour décider "
                 "sur quelle recherche montrer la page — et ce que le client lit pour décider de cliquer.",
    },
    "eeat": {
        "label": "E-E-A-T",
        "subtitle": "Ce qui établit la crédibilité du site aux yeux de Google",
        "intro": "Expérience, Expertise, Autorité, Fiabilité : les quatre critères que Google demande "
                 "à ses évaluateurs de vérifier. Qui est derrière le site, peut-on le joindre, "
                 "qui se porte garant de ce qui est écrit.",
    },
}

#: Chaque vérification : son pilier, ce qu'on dit quand elle passe, et les
#: constats qu'elle peut produire. Une vérification qui passe est montrée au
#: client — un audit qui ne liste que des défauts ne dit pas la vérité.
CHECKS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    # Technique
    "domaine": ("technique", "Les deux versions de l'adresse (avec et sans « www ») mènent au site",
                ("domaine-injoignable",)),
    "domaine-unique": ("technique", "Une seule version du domaine est servie, l'autre y redirige",
                       ("domaine-duplique",)),
    "https": ("technique", "La connexion sécurisée (https) est imposée", ("http-sans-redirection",)),
    "robots": ("technique", "Fichier robots.txt présent", ("robots-absent",)),
    "sitemap": ("technique", "Plan du site (sitemap.xml) présent", ("sitemap-absent",)),
    "llms": ("technique", "Fichier llms.txt présent pour les IA", ("llms-absent",)),
    "erreurs": ("technique", "Aucune page en erreur parmi les pages lues", ("pages-cassees",)),
    "canonique": ("technique", "Adresse canonique déclarée sur chaque page", ("canonical-absente",)),
    "indexation": ("technique", "Aucune page exclue de Google (noindex)", ("noindex",)),
    "langue": ("technique", "Langue déclarée sur chaque page", ("lang-absente",)),
    "mobile": ("technique", "Pages adaptées à l'affichage sur téléphone", ("viewport-absent",)),
    "doublons": ("technique", "Aucune page publiée en plusieurs exemplaires", ("page-doublon",)),
    "jsonld-valide": ("technique", "Données structurées bien formées", ("jsonld-invalide",)),
    "vitesse": ("technique", "Site rapide sur mobile (note PageSpeed de 90 ou plus)",
                ("vitesse-mobile-lente", "vitesse-mobile-moyenne")),
    "cwv": ("technique", "Core Web Vitals validés par Google sur les visiteurs réels", ("cwv-echec",)),
    # On-Page
    "titres": ("on-page", "Chaque page a un titre", ("title-absent",)),
    "titres-longueur": ("on-page", "Titres de bonne longueur", ("title-court", "title-long")),
    "titres-uniques": ("on-page", "Chaque page a un titre qui lui est propre", ("title-duplique",)),
    "meta": ("on-page", "Chaque page a une meta description", ("meta-absente",)),
    "meta-uniques": ("on-page", "Meta descriptions toutes différentes", ("meta-dupliquee",)),
    "h1": ("on-page", "Un titre principal (H1) sur chaque page", ("h1-absent",)),
    "h1-unique": ("on-page", "Un seul H1 par page", ("h1-multiple",)),
    "h1-propre": ("on-page", "Titres principaux propres", ("h1-casse",)),
    "contenu": ("on-page", "Pages suffisamment rédigées (150 mots ou plus)", ("contenu-mince",)),
    "partage": ("on-page", "Aperçu prévu pour les partages (Open Graph)", ("og-absent",)),
    "images": ("on-page", "Images décrites par un texte alternatif", ("images-sans-alt",)),
    "reponses": ("on-page", "Réponses structurées (FAQ…) que les IA peuvent citer", ("geo-pas-de-reponses",)),
    # E-E-A-T
    "brouillons": ("eeat", "Aucune page brouillon en ligne", ("page-brouillon",)),
    "entreprise": ("eeat", "L'entreprise est décrite aux machines (données structurées)",
                   ("jsonld-absent", "jsonld-entreprise")),
    "profils": ("eeat", "L'identité est reliée aux profils officiels (sameAs)", ("jsonld-sameas",)),
    "contact": ("eeat", "Une page contact (ou de demande de devis) est accessible", ("page-contact",)),
    "a-propos": ("eeat", "Une page présente l'entreprise (à propos)", ("page-a-propos",)),
    "mentions": ("eeat", "Mentions légales accessibles", ("mentions-legales",)),
    "confidentialite": ("eeat", "Politique de confidentialité accessible", ("confidentialite",)),
    "coordonnees": ("eeat", "Téléphone ou e-mail visible sur le site", ("coordonnees-absentes",)),
    "auteurs": ("eeat", "Les articles indiquent leur auteur", ("auteur-absent",)),
    "dates": ("eeat", "Les articles sont datés", ("date-absente",)),
    "relecture": ("eeat", "Les pages santé indiquent qui les a relues", ("relecture-medicale",)),
    "mention-credit": ("eeat", "Mention légale du crédit présente sur les pages de crédit à la consommation",
                       ("mention-credit",)),
}
CHECK_OF = {code: check for check, (_, _, codes) in CHECKS.items() for code in codes}
PILLAR_OF = {code: CHECKS[check][0] for code, check in CHECK_OF.items()}

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
    pillar: str = ""

    def __post_init__(self) -> None:
        if not self.pillar:
            self.pillar = PILLAR_OF.get(self.code, "technique")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditResult:
    url: str
    pages: list[Page]
    findings: list[Finding]
    score: int
    evaluated: set[str] = field(default_factory=set)
    speed: list[pagespeed.Speed] = field(default_factory=list)
    sector: str = ""
    crawler: str = "agent-growth"       # ou "screaming-frog"
    pages_crawled: int = 0              # pages lues par le crawler retenu
    created_at: str = field(default_factory=lambda: date.today().isoformat())

    @property
    def counts(self) -> dict[str, int]:
        c = Counter(f.severity for f in self.findings)
        return {s: c.get(s, 0) for s in ("critique", "important", "amelioration")}

    def to_dict(self) -> dict:
        """Tout ce qu'il faut pour refaire le rapport plus tard, sans relire le site."""
        return {
            "url": self.url, "score": self.score, "created_at": self.created_at,
            "sector": self.sector, "crawler": self.crawler,
            "pages": self.pages_crawled or len(self.pages),
            "page_urls": [p.url for p in self.pages],
            "counts": self.counts,
            "evaluated": sorted(self.evaluated),
            "findings": [f.to_dict() for f in self.findings],
            "speed": [s.to_dict() for s in self.speed],
        }


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


def site_checks(root_url: str, client: httpx.Client, evaluated: set[str] | None = None) -> list[Finding]:
    evaluated = set() if evaluated is None else evaluated
    evaluated.update({"domaine", "https", "robots", "sitemap", "llms"})
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
        evaluated.add("domaine-unique")
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


def page_checks(pages: list[Page], evaluated: set[str] | None = None, *,
                only: frozenset[str] | None = None, skip: frozenset[str] = frozenset()) -> list[Finding]:
    """Règles page par page. `only` et `skip` partagent le travail entre deux
    sources : l'export Screaming Frog pour ce qu'il couvre, notre crawl pour le reste."""
    evaluated = set() if evaluated is None else evaluated
    readable = [p for p in pages if not p.error and p.seo is not None]
    # Une page brouillon a un seul vrai problème : être en ligne. La signaler
    # aussi pour son titre ou sa meta gonflerait l'audit de bruit.
    drafts = [p.url for p in readable if p.seo.title and PLACEHOLDER.match(p.seo.title.strip())]
    ok = [p for p in readable if p.url not in drafts]
    findings: list[Finding] = []

    def wanted(code: str) -> bool:
        return (only is None or code in only) and code not in skip

    def add(code, severity, category, title, why, fix, urls):
        if not wanted(code):
            return
        evaluated.add(CHECK_OF[code])
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
    # Une règle appelée avec une liste vide « passe » : elle est montrée au
    # client comme un point acquis.
    all_types = {t for p in ok for t in p.seo.jsonld_types}
    home = [ok[0].url] if ok else []
    if ok:
        add("jsonld-absent", "important", "geo", "Aucune donnée structurée sur le site",
            "Les données structurées disent aux machines, sans ambiguïté : qui vous êtes, ce que vous "
            "vendez, à quel prix, où. Sans elles, Google et les IA déduisent — et se trompent.",
            "Ajouter au minimum un bloc Organization (ou le type de votre activité) sur l'accueil, "
            "et FAQPage sur les pages qui répondent à des questions.",
            home if not all_types else [])
        add("jsonld-entreprise", "important", "geo", "L'entreprise n'est pas décrite pour les machines",
            "Des données structurées existent, mais aucune ne dit qui vous êtes : nom, activité, contact.",
            "Ajouter un bloc Organization ou le type précis de l'activité sur l'accueil.",
            home if all_types and not (all_types & BUSINESS_TYPES) else [])
    if ok and all_types:
        add("geo-pas-de-reponses", "amelioration", "geo", "Aucune page de réponses structurées",
            "Les IA citent volontiers une réponse claire à une question précise. Une FAQ balisée "
            "est l'un des formats qu'elles reprennent le plus facilement.",
            "Ajouter une FAQ balisée (FAQPage) sur les pages d'offre.",
            home if not (all_types & ANSWER_TYPES) else [])
    add("jsonld-invalide", "important", "geo", "Données structurées illisibles",
        "Un bloc mal formé est ignoré en entier par Google.",
        "Corriger le JSON (le tester dans l'outil de test des résultats enrichis de Google).",
        [p.url for p in ok if "JSON-LD invalide" in p.seo.jsonld_types])
    return findings


# --------------------------------------------------------------------------- #
# E-E-A-T : la crédibilité
# --------------------------------------------------------------------------- #

#: Pages de confiance : (adresse, intitulé du lien).
TRUST_PAGES = {
    "page-contact": (r"/(contact|nous-contacter|contactez-nous|devis|rendez-vous|prise-de-rendez-vous)",
                     r"\bcontact|\bdevis\b|rendez-vous"),
    "page-a-propos": (r"/(a-propos|about|qui-sommes-nous|notre-histoire|notre-equipe|equipe|a-pro\w*-de)",
                      r"(à|a) propos|qui sommes|notre (histoire|équipe)|\babout\b"),
    "mentions-legales": (r"/(mentions-legales|legal|imprint|informations-legales)",
                         r"mentions l[ée]gales|informations l[ée]gales|legal notice"),
    "confidentialite": (r"/(confidentialit|privacy|donnees-personnelles|protection-des-donnees|rgpd)",
                        r"confidentialit|données personnelles|vie privée|privacy|rgpd"),
}

ARTICLE_TYPES = {"Article", "BlogPosting", "NewsArticle"}
ARTICLE_PATH = re.compile(r"/(blog|actualites?|articles?|news|conseils|guides?|magazine)/[^/]+", re.I)

#: Secteurs où Google applique ses exigences de crédibilité les plus strictes
#: (« Your Money or Your Life » : la santé et l'argent des gens).
SECTORS = {
    "sante": re.compile(r"\b(chirurgi\w*|médic\w*|clinique\w*|santé|patient\w*|anesthési\w*|dentaire|"
                        r"esthétique|médecin\w*)\b", re.I),
    "finance": re.compile(r"\b(banque\w*|bancaire\w*|crédit\w*|prêts?|assurance\w*|épargne|"
                          r"placement\w*|investissement\w*)\b", re.I),
}
SECTOR_LABEL = {"sante": "la santé", "finance": "l'argent (banque, crédit, assurance)"}


def sector(pages: list[Page]) -> str:
    """« sante », « finance » ou « » d'après l'accueil. Trois mentions au moins."""
    home = next((p for p in pages if p.seo), None)
    if home is None:
        return ""
    text = " ".join([home.seo.title, *home.seo.h1, home.text[:4000]])
    hits = {name: len(rx.findall(text)) for name, rx in SECTORS.items()}
    best = max(hits, key=hits.get)
    return best if hits[best] >= 3 else ""


def eeat_checks(pages: list[Page], evaluated: set[str] | None = None, *, sector_name: str = "") -> list[Finding]:
    evaluated = set() if evaluated is None else evaluated
    readable = [p for p in pages if not p.error and p.seo is not None]
    if not readable:
        return []
    findings: list[Finding] = []

    def add(code, severity, title, why, fix, urls, category="contenu"):
        evaluated.add(CHECK_OF[code])
        if urls:
            findings.append(Finding(code, severity, category, title, why, fix, sorted(set(urls))))

    home = readable[0].url
    paths = [urlparse(u).path.lower() for p in readable for u in (p.url, *p.links)]
    labels = [label for p in readable for label in p.seo.link_labels]

    def found(code: str) -> bool:
        path_rx, label_rx = TRUST_PAGES[code]
        return any(re.search(path_rx, x) for x in paths) or any(re.search(label_rx, x) for x in labels)

    add("page-contact", "important", "Pas de page contact trouvée",
        "Un visiteur qui hésite cherche d'abord comment vous joindre. Les consignes de Google à ses "
        "évaluateurs demandent la même chose : pouvoir contacter le responsable du site.",
        "Créer une page « Contact » reliée depuis le menu ou le pied de page : téléphone, e-mail, adresse, horaires.",
        [] if found("page-contact") else [home])
    add("page-a-propos", "important", "Pas de page « À propos »",
        "Qui êtes-vous, depuis quand, qui est derrière l'entreprise : c'est la première page qu'ouvre "
        "un client prudent, et celle que Google et les IA lisent pour savoir à qui ils ont affaire.",
        "Créer une page « À propos » : l'histoire, l'équipe avec noms et fonctions, les preuves vérifiables.",
        [] if found("page-a-propos") else [home])
    add("mentions-legales", "important", "Pas de mentions légales accessibles",
        "En France, la loi pour la confiance dans l'économie numérique (LCEN) impose d'indiquer qui "
        "édite le site : raison sociale, adresse, responsable de la publication, hébergeur. Leur absence "
        "est sanctionnable et fait douter du sérieux de l'entreprise.",
        "Publier une page « Mentions légales » reliée depuis le pied de page de chaque page.",
        [] if found("mentions-legales") else [home])
    add("confidentialite", "important", "Pas de politique de confidentialité accessible",
        "Dès qu'un formulaire recueille un nom ou un e-mail, le RGPD impose d'expliquer ce que deviennent "
        "ces données. C'est aussi la page que lit un client prudent avant de laisser ses coordonnées.",
        "Publier une « Politique de confidentialité » reliée depuis le pied de page et depuis chaque formulaire.",
        [] if found("confidentialite") else [home])

    keys = {k for p in readable for k in p.seo.jsonld_keys}
    reachable = any(p.seo.has_tel or p.seo.has_email or p.seo.has_phone_text for p in readable) \
        or bool(keys & {"telephone", "email"})
    add("coordonnees-absentes", "important", "Aucun téléphone ni e-mail visible",
        "Ni numéro, ni adresse e-mail sur les pages lues. Une entreprise qu'on ne peut pas joindre "
        "directement inspire moins confiance, à un client comme à Google.",
        "Afficher un téléphone et un e-mail cliquables dans le pied de page de toutes les pages.",
        [] if reachable else [home])

    types = {t for p in readable for t in p.seo.jsonld_types}
    if types & BUSINESS_TYPES:
        add("jsonld-sameas", "amelioration", "L'identité n'est pas reliée aux profils officiels",
            "La propriété « sameAs » relie le site aux profils officiels de l'entreprise (LinkedIn, "
            "fiche Google, réseaux sociaux). Google et les IA s'en servent pour confirmer qu'il s'agit "
            "bien de la même entreprise.",
            "Ajouter « sameAs » au bloc de l'entreprise, avec l'adresse de chaque profil officiel.",
            [] if "sameAs" in keys else [home], category="geo")

    drafts = {p.url for p in readable if p.seo.title and PLACEHOLDER.match(p.seo.title.strip())}
    articles = [p for p in readable if p.url not in drafts and (
        set(p.seo.jsonld_types) & ARTICLE_TYPES or ARTICLE_PATH.search(urlparse(p.url).path))]
    if articles:
        add("auteur-absent", "important" if sector_name else "amelioration", "Articles sans auteur identifié",
            "Un conseil sans signature ne prouve aucune expertise. Google cherche qui a écrit, et à quel "
            "titre il peut en parler — plus encore sur les sujets qui touchent à la santé ou à l'argent.",
            "Signer chaque article : nom, fonction, une ligne sur l'expérience de l'auteur, et le "
            "déclarer dans les données structurées (author).",
            [p.url for p in articles if "author" not in p.seo.jsonld_keys and not p.seo.has_author_meta])
        add("date-absente", "amelioration", "Articles sans date",
            "Un lecteur ne sait pas si l'information est à jour. Google et les IA préfèrent les contenus "
            "dont la fraîcheur est vérifiable.",
            "Afficher la date de publication et de mise à jour, et la déclarer (datePublished, dateModified).",
            [p.url for p in articles if not (set(p.seo.jsonld_keys) & {"datePublished", "dateModified"})
             and not p.seo.has_date_meta])

    if sector_name == "sante":
        medical = [p for p in readable if "MedicalWebPage" in p.seo.jsonld_types]
        if medical:
            add("relecture-medicale", "amelioration", "Pages santé sans relecteur identifié",
                "Sur la santé, Google veut savoir quel professionnel se porte garant de l'information. "
                "Les données structurées permettent de le dire : relu par qui, et quand.",
                "Ajouter « reviewedBy » (le professionnel qui a validé le contenu, avec sa spécialité exacte) "
                "et « lastReviewed » sur chaque page santé.",
                [p.url for p in medical if not set(p.seo.jsonld_keys) & {"reviewedBy", "lastReviewed"}])

    if sector_name == "finance":
        # L312-5 vise le crédit à la consommation. Crédit immobilier et crédit
        # professionnel ont leurs propres règles : on ne les juge pas sur celle-ci.
        credit = [p for p in readable if p.url not in drafts
                  and re.search(r"credit|pret", urlparse(p.url).path, re.I)
                  and not re.search(r"logement|immobili|habitat|aeras|professionnel|entreprise|/pro\b",
                                    urlparse(p.url).path, re.I)]
        if credit:
            add("mention-credit", "important", "Pages de crédit sans la mention légale obligatoire",
                "Toute publicité pour un crédit à la consommation doit afficher : « Un crédit vous engage "
                "et doit être remboursé. Vérifiez vos capacités de remboursement avant de vous engager. » "
                "(Code de la consommation, art. L312-5). Ces pages ne la portent pas dans sa formulation "
                "exacte — une paraphrase ne suffit pas.",
                "Ajouter la mention exacte, lisible, sur chaque page qui présente un crédit à la "
                "consommation, et faire valider la liste complète des mentions obligatoires (crédit "
                "immobilier compris) par la conformité.",
                [p.url for p in credit if not p.seo.credit_warning])
    return findings


# --------------------------------------------------------------------------- #
# Vitesse (PageSpeed Insights)
# --------------------------------------------------------------------------- #

def speed_targets(pages: list[Page], extra: int = 2) -> list[tuple[str, pagespeed.Strategy]]:
    """L'accueil sur mobile et ordinateur, plus les pages qui vendent, sur mobile."""
    readable = [p for p in pages if not p.error and p.seo is not None]
    if not readable:
        return []
    home = readable[0].url
    ranked = [url for url, _ in _rank_links([p.url for p in readable[1:]], home)][:extra]
    return [(home, "mobile"), (home, "desktop"), *[(u, "mobile") for u in ranked]]


def speed_checks(speeds: list[pagespeed.Speed], evaluated: set[str] | None = None) -> list[Finding]:
    evaluated = set() if evaluated is None else evaluated
    mobile = [s for s in speeds if s.strategy == "mobile" and not s.error and s.score is not None]
    findings: list[Finding] = []
    if mobile:
        evaluated.add("vitesse")
        slow = [s.url for s in mobile if s.score < 50]
        average = [s.url for s in mobile if 50 <= s.score < 90]
        if slow:
            findings.append(Finding(
                "vitesse-mobile-lente", "important", "technique", "Le site est lent sur téléphone",
                "Note PageSpeed sous 50/100 sur mobile. Plus une page met de temps à s'afficher, plus "
                "de visiteurs repartent avant de l'avoir vue — et la majorité navigue sur téléphone.",
                "Commencer par les pistes listées dans le tableau de vitesse : ce sont celles que Google "
                "chiffre comme les plus rentables.", slow))
        if average:
            findings.append(Finding(
                "vitesse-mobile-moyenne", "amelioration", "technique", "Vitesse mobile perfectible",
                "Note PageSpeed entre 50 et 89/100 sur mobile : correct, mais pas encore dans la zone "
                "« rapide » de Google (90 et plus).",
                "Appliquer les pistes du tableau de vitesse, page par page.", average))
    measured = [s for s in speeds if s.field_data]
    if measured:
        evaluated.add("cwv")
        failed = sorted({s.url for s in measured if s.cwv_passed is False})
        if failed:
            findings.append(Finding(
                "cwv-echec", "important", "technique", "Core Web Vitals non validés par Google",
                "Les Core Web Vitals sont trois mesures prises par Google sur les vrais visiteurs : "
                "le temps d'affichage du contenu principal, la réactivité aux clics, la stabilité de la "
                "page. Google ne les valide pas ici, et en tient compte dans son classement.",
                "Voir dans le tableau de vitesse quelle mesure est hors seuil, et la traiter en premier.",
                failed))
    return findings


# --------------------------------------------------------------------------- #
# Lancement
# --------------------------------------------------------------------------- #

def pillar_score(findings: list[Finding]) -> int:
    """Note sur 100 d'un pilier. Chaque constat pèse selon sa gravité,
    multiplié — avec un plafond — par le nombre de pages touchées.

    La pénalité est amortie plutôt que soustraite : au-delà d'une dizaine de
    constats, une soustraction donne 0 à tous les sites, qui ne se distinguent
    plus entre eux ; et un « 0/100 » dans un audit envoyé ressemble à une
    provocation, pas à un diagnostic.
    """
    import math

    penalty = sum(SEVERITY_WEIGHT[f.severity] * min(1 + len(f.urls) / 10, 2) for f in findings)
    return round(100 * math.exp(-penalty / 40))


def pillar_scores(findings: list[Finding]) -> dict[str, int]:
    return {key: pillar_score([f for f in findings if f.pillar == key]) for key in PILLARS}


def score(findings: list[Finding]) -> int:
    """Note globale : la moyenne des trois piliers. Un client qui lit 80, 90 et
    70 doit retrouver 80 en haut du rapport, pas un chiffre qu'il ne sait pas
    expliquer."""
    scores = pillar_scores(findings)
    return round(sum(scores.values()) / len(scores))


def _variants(url: str) -> list[str]:
    """L'adresse donnée d'abord, puis l'autre version du domaine."""
    parsed = urlparse(url)
    host = parsed.netloc
    other = host[4:] if host.startswith("www.") else f"www.{host}"
    path = parsed.path or "/"
    return [url, f"https://{other}{path}"]


def run(url: str, *, max_pages: int = 40, client: httpx.Client | None = None,
        speed: bool = True, speed_client: httpx.Client | None = None, lighthouse=None,
        screaming_frog: str | None = None) -> AuditResult:
    """Lance l'audit complet.

    `screaming_frog` : chemin d'un export « Internal: All ». Il remplace notre
    crawl pour les règles qu'il couvre ; notre crawl reste lu pour le reste.
    `lighthouse` : remplace le lancement de Lighthouse (tests).
    """
    from . import screamingfrog

    if not urlparse(url).scheme:
        url = f"https://{url}"
    own = client is None
    client = client or httpx.Client(timeout=20.0, follow_redirects=True,
                                    headers={"User-Agent": USER_AGENT,
                                             "Accept-Language": "fr-FR,fr;q=0.9"})
    evaluated: set[str] = set()
    speeds: list[pagespeed.Speed] = []
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
        found_sector = sector(pages)
        findings = site_checks(root, client, evaluated)
        if screaming_frog:
            sf_pages = screamingfrog.load(screaming_frog)
            findings += page_checks(sf_pages, evaluated, only=screamingfrog.COVERED)
            findings += page_checks(pages, evaluated, skip=screamingfrog.COVERED)
        else:
            sf_pages = []
            findings += page_checks(pages, evaluated)
        findings += eeat_checks(pages, evaluated, sector_name=found_sector)
        if speed:
            speeds = pagespeed.measure_all(speed_targets(pages), client=speed_client or client,
                                           runner=lighthouse)
            findings += speed_checks(speeds, evaluated)
    finally:
        if own:
            client.close()
    order = {"critique": 0, "important": 1, "amelioration": 2}
    findings.sort(key=lambda f: (order[f.severity], -len(f.urls)))
    return AuditResult(url=url, pages=pages, findings=findings, score=score(findings),
                       evaluated=evaluated, speed=speeds, sector=found_sector,
                       crawler="screaming-frog" if sf_pages else "agent-growth",
                       pages_crawled=len(sf_pages) or len(pages))


# --------------------------------------------------------------------------- #
# Recherche Google manuelle
# --------------------------------------------------------------------------- #

def _google(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}&hl=fr&gl=fr"


def manual_checklist(url: str, *, brand: str = "") -> list[dict]:
    """Les vérifications que seul un humain peut faire : regarder Google.

    On n'automatise pas ces recherches — les conditions d'utilisation de Google
    l'interdisent, et un résultat lu par le consultant vaut mieux qu'un résultat
    aspiré. Comptez un quart d'heure. Chaque vérification se remplit avec :
    `status` (« ok », « a-ameliorer » ou « probleme ») et `constat`, la phrase
    que lira le client.
    """
    domain = urlparse(url if urlparse(url).scheme else f"https://{url}").netloc.removeprefix("www.")
    name = brand or domain.split(".")[0]

    def item(id_: str, pillar: str, question: str, how: str, links: list[dict]) -> dict:
        return {"id": id_, "pillar": pillar, "question": question, "how": how, "links": links,
                "status": "", "constat": ""}

    return [
        item("indexation", "technique", "Combien de pages Google connaît-il ?",
             "Lancer la recherche ci-dessous et noter le nombre de résultats. Le comparer au nombre de "
             "pages lues par le crawl : beaucoup moins = pages ignorées par Google ; beaucoup plus = "
             "pages parasites indexées (anciennes pages, brouillons, filtres).",
             [{"label": f"site:{domain}", "url": _google(f"site:{domain}")}]),
        item("requete-marque", "eeat", "Que voit un client qui tape le nom de la marque ?",
             "Le site sort-il en premier ? Les liens annexes (pages du site sous le premier résultat) "
             "sont-ils pertinents ? Y a-t-il un résultat négatif ou un concurrent en première page ?",
             [{"label": name, "url": _google(name)}]),
        item("fiche-google", "eeat", "La fiche Google de l'entreprise existe-t-elle, et est-elle complète ?",
             "Ouvrir Google Maps : fiche présente, catégorie juste, horaires, site, photos récentes, "
             "réponses aux avis.",
             [{"label": f"{name} sur Google Maps",
               "url": f"https://www.google.com/maps/search/{quote_plus(name)}"}]),
        item("avis", "eeat", "Que disent les avis en ligne ?",
             "Note moyenne et nombre d'avis, sur Google et ailleurs. L'entreprise répond-elle ? "
             "Noter les reproches qui reviennent : ce sont des objections à traiter sur le site.",
             [{"label": f"{name} avis", "url": _google(f"{name} avis")}]),
        item("requete-metier", "on-page", "Le site sort-il sur la recherche principale d'un client ?",
             "Choisir la recherche qu'un client ferait sans connaître la marque (service + lieu), "
             "l'écrire dans le constat, et noter la position du site et les trois premiers concurrents.",
             [{"label": "Recherche Google", "url": "https://www.google.com/"}]),
        item("ia", "eeat", "Les assistants IA recommandent-ils la marque ?",
             "Poser la même question métier à ChatGPT et à Perplexity : la marque est-elle citée ? "
             "Qui l'est à sa place, et sur la foi de quelles sources ?",
             [{"label": "ChatGPT", "url": "https://chatgpt.com/"},
              {"label": "Perplexity", "url": "https://www.perplexity.ai/"}]),
    ]


MANUAL_STATUS = {"ok": "Bon point", "a-ameliorer": "À améliorer", "probleme": "Problème"}


# --------------------------------------------------------------------------- #
# Le rapport client
# --------------------------------------------------------------------------- #

SEVERITY_LABEL = {"critique": "Critique", "important": "Important", "amelioration": "Amélioration"}
HORIZON = {"critique": "Cette semaine", "important": "Ce mois-ci", "amelioration": "Ensuite"}


def report(data: dict, manual: list[dict] | None = None, *, brand: str = "") -> dict:
    """Met en forme un audit (`AuditResult.to_dict()`) pour le rapport client.

    Le rapport n'est « prêt à envoyer » que si chaque vérification manuelle a été
    faite : sinon il porte la mention « version de travail », y compris à
    l'impression, pour qu'il ne parte pas par erreur.
    """
    findings = [Finding(**f) for f in data["findings"]]
    evaluated = set(data.get("evaluated", []))
    manual = manual if manual is not None else manual_checklist(data["url"], brand=brand)
    done = [m for m in manual if m.get("status") in MANUAL_STATUS and m.get("constat", "").strip()]
    pending = [m for m in manual if m not in done]
    flagged = {f.code for f in findings}

    pillars = []
    for key, meta in PILLARS.items():
        own = [f for f in findings if f.pillar == key]
        passed = [label for check, (pillar, label, codes) in CHECKS.items()
                  if pillar == key and check in evaluated and not flagged & set(codes)]
        pillars.append({
            "key": key, **meta, "score": pillar_score(own),
            "findings": [{**f.to_dict(), "severity_label": SEVERITY_LABEL[f.severity],
                          "geo": f.category == "geo"} for f in own],
            "passed": passed,
            "manual": [{**m, "status_label": MANUAL_STATUS[m["status"]]} for m in done if m["pillar"] == key],
            "speed": data.get("speed", []) if key == "technique" else [],
        })

    plan = [{"horizon": HORIZON[f.severity], "title": f.title, "pillar": PILLARS[f.pillar]["label"],
             "pages": len(f.urls)} for f in findings]
    speeds = data.get("speed", [])
    speed_sources = {s["source"] for s in speeds if s.get("source")}
    crawler = data.get("crawler", "agent-growth")
    tools = [{
        "name": "Crawl complet du site",
        "by": "Screaming Frog SEO Spider" if crawler == "screaming-frog" else "Robot d'exploration Agent Growth",
        "detail": f"{data['pages']} pages lues une à une, comme le fait Google : codes de réponse, titres, "
                  "descriptions, titres principaux, contenu, adresses canoniques, indexation"
                  + (", complété par notre robot pour les données structurées et les signaux de confiance."
                     if crawler == "screaming-frog" else ", données structurées, signaux de confiance.")
                  + " Le fichier robots.txt du site est respecté.",
    }]
    if speeds:
        tools.append({
            "name": "Google PageSpeed Insights",
            "by": "API PageSpeed Insights" if speed_sources == {"pagespeed"}
            else "Lighthouse, le moteur de PageSpeed Insights" if speed_sources == {"lighthouse"}
            else "PageSpeed Insights et Lighthouse",
            "detail": "Vitesse de chargement mesurée sur mobile et sur ordinateur, avec les mêmes règles "
                      "et la même note que Google."
                      + (" Données des visiteurs réels (Core Web Vitals) issues du rapport Chrome de Google."
                         if any(s.get("field_data") for s in speeds) else ""),
        })
    tools.append({
        "name": "Recherche Google manuelle",
        "by": "Faite à la main par votre consultant",
        "detail": "Ce que voit un client sur Google : pages indexées, recherche sur la marque, fiche Google, "
                  "avis, position sur la recherche métier, et recommandations des assistants IA.",
    })

    return {
        "url": data["url"], "domain": urlparse(data["url"]).netloc.removeprefix("www."),
        "brand": brand, "date": data.get("created_at", ""),
        "score": data["score"], "pages": data["pages"], "counts": data.get("counts", {}),
        "sector": SECTOR_LABEL.get(data.get("sector", ""), ""),
        "pillars": pillars, "plan": plan, "tools": tools,
        "draft": bool(pending), "pending": pending,
        "top": plan[:3],
    }
