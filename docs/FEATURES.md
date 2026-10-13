# Fonctionnalités clés

Document de référence du périmètre. Il répond à trois questions : qu'est-ce
qu'on construit, dans quel ordre, et pourquoi dans cet ordre.

## Le principe qui commande tout le reste

Un agent growth qui écrit un post Instagram le lundi et une annonce Google le
mardi produit deux marques différentes. Le seul moyen d'éviter ça est de sortir
le positionnement, le ton et les piliers de contenu des prompts, et de les
mettre dans **un fichier que tous les outils lisent** : `brand-core.json`.

```
                      ┌─────────────────────┐
                      │   brand-core.json   │   ← la ligne éditoriale
                      │  (ligne éditoriale) │     comme contrat
                      └──────────┬──────────┘
          ┌──────────────┬───────┴───────┬──────────────┐
          ▼              ▼               ▼              ▼
     ┌─────────┐   ┌──────────┐    ┌─────────┐   ┌───────────┐
     │ SEO/GEO │   │  Social  │    │   Ads   │   │ Outbound  │
     │  Site   │   │   GMB    │    │ Visuels │   │ Séquences │
     └────┬────┘   └────┬─────┘    └────┬────┘   └─────┬─────┘
          └─────────────┴───────┬───────┴──────────────┘
                                ▼
                    ┌───────────────────────┐
                    │ Cohérence + Mesure    │
                    └───────────────────────┘
```

Aucun outil ne redécide du ton. S'il en a besoin, il le lit. C'est ce qui rend
la « cohérence globale » mécanique au lieu d'être un vœu.

## Les sept règles de conception

Elles valent pour chaque outil ajouté au projet.

1. **La ligne éditoriale est un contrat, pas une suggestion.** Un outil qui
   produit du contenu lit `brand-core.json` et s'y conforme. S'il veut s'en
   écarter, il le dit explicitement et explique pourquoi.
2. **Aucun chiffre sans ses hypothèses.** Toute estimation est une fourchette,
   accompagnée des hypothèses qui la soutiennent et de son origine (`lu sur le
   site`, `benchmark secteur`, `hypothèse`). Un ordre de grandeur assumé est
   utile ; un chiffre faussement précis détruit la confiance.
3. **Vulgariser est une fonctionnalité, pas de la mise en forme.** La cible est
   un dirigeant sans formation marketing. Chaque recommandation porte une
   version en français clair et une première action faisable cette semaine.
4. **Rien ne part sans validation humaine.** Publier, dépenser, contacter : ces
   trois actions passent par un « oui » explicite. Cette porte ne s'ouvre
   qu'outil par outil, et sur demande du client.
5. **Un outil = un fichier lisible en entrée, un fichier lisible en sortie.**
   Pas d'état caché, pas de base de données tant qu'un dossier de fichiers
   suffit. On peut relire, corriger à la main, versionner, montrer au client.
6. **Pré-tester avant de dépenser.** Jeter trois accroches coûte moins cher
   qu'une campagne qui ne parle à personne. Tout outil qui produit une création
   produit des variantes et les confronte avant diffusion.
7. **Ne pas écrire ce qui existe déjà sous licence MIT.** Le savoir marketing
   est abondant, gratuit et mieux maintenu que ce qu'on produirait (ADR-009).
   Avant d'ouvrir un fichier, on vérifie si une skill le fait déjà. Si oui, on
   la vendorise et on écrit le pont.

## État d'avancement

| Statut | Signification |
| --- | --- |
| ✅ | Livré et testé |
| 🔜 | Prochain lot |
| ⬜ | Planifié |
| ♻ | **Ne pas écrire — vendoriser** (ADR-009) |
| 🔒 | Bloqué par un accès externe (API, compte, contrat) |

## La contrainte qui commande le périmètre

Le modèle retenu est un abonnement à prix bas avec un humain responsable
derrière (ADR-008). Dans ce modèle, la variable qui décide de tout n'est ni le
prix ni le nombre de fonctionnalités : c'est **le nombre d'heures de livraison
par client et par mois.**

À 250 €/mois, une heure et demie de travail humain mensuel laisse une marge.
Quatre heures n'en laissent aucune. Le prix de vente ne peut pas monter — c'est
précisément le trou de marché qu'on occupe — donc la seule variable ajustable
est le temps.

**Conséquence : chaque outil se juge sur une seule question — combien d'heures
par client et par mois est-ce que ça m'enlève ?** Un outil qui produit une
analyse brillante une fois vaut moins qu'un outil qui supprime deux heures
tous les mois. C'est ce critère qui a réordonné les lots ci-dessous, et non
l'exhaustivité marketing.

Le second levier est la **spécialisation sur un métier** : à secteur identique,
les piliers, les clusters SEO, les concurrents et les objections se réutilisent
d'un client à l'autre. Le deuxième client d'un même métier coûte la moitié du
temps du premier. C'est le réducteur d'heures le plus puissant du modèle, et il
ne demande aucune ligne de code.

---

## Socle — la ligne éditoriale

### ✅ `brand-core` — construire l'ADN de la marque

Lit le site de la marque et ceux de ses concurrents, puis produit :

- le positionnement et la catégorie dans laquelle le client la range ;
- les ICP, avec pour chacun **ce qu'il tape sur Google** (matière du SEO) et
  **où il se trouve** (matière de l'outbound) ;
- l'analyse concurrentielle et l'espace laissé libre ;
- la ligne éditoriale : mission, promesse, preuves, curseurs de ton, vocabulaire
  à employer et à bannir, piliers de contenu avec leur part de voix, formats
  signature, interdits ;
- les angles différenciants, avec la preuve à réunir et le risque ;
- **6 à 10 opportunités chiffrées** par canal, classées par rentabilité ;
- les questions ouvertes — ce qui n'a pas pu être déduit.

Produit `brand-core.json` (le contrat), `brand-core.md` (le document que le
client lit) et `voice.md` (la fiche de voix des outils de rédaction).

Ce qui le distingue des documents de contexte équivalents (ADR-009) : il est
**rempli par un crawl, pas par un entretien**. Un dirigeant de TPE ne remplira
jamais un questionnaire en douze sections ; c'est ce qui rend l'onboarding
possible, pas un confort d'ergonomie.

### 🔜 `brand-core export` — le pont vers les skills vendorisées

**Le prochain outil à écrire, et de loin le meilleur rapport effort/effet.**

Les librairies de skills marketing attendent conventionnellement un document de
contexte partagé (`.agents/product-marketing.md`) que toutes consultent avant
d'agir. `brand-core` possède déjà cette information, en mieux structuré.

Un pont de quelques heures fait donc hériter **~40 skills** de la marque, sans
aucune saisie du client. C'est le levier qui transforme un outil en couverture
marketing complète.

À reprendre d'elles au passage, parce que c'est meilleur que ce qu'on a :
versionnage avec journal des changements, anti-personas, dynamiques de bascule
(poussée, attraction, habitude, anxiété), langage client verbatim.

### ⬜ `brand-core refresh`

Relancer l'analyse sans perdre les corrections humaines.

---

## Lot 1 — Réduire l'heure de livraison, et mener avec le GEO

C'est le lot qui crée la marge et qui porte l'argument de vente. Rien d'autre
ne passe devant. L'ordre vient de [l'étude de marché](ETUDE-MARCHE.md).

### ⬜ `geo-audit` — être cité par les IA

**Promu en tête : c'est désormais l'argument principal de l'offre** (ADR-010).
Le CTR organique perd 58 à 61 % sur les requêtes à réponse IA, et l'effet
accélère ; le retainer médian GEO/AEO est à 6 850 $/mois, +66 % en deux ans.

Interroger les assistants (ChatGPT, Claude, Perplexity, AI Overviews) sur les
requêtes de l'ICP, relever qui est cité et avec quelle formulation, puis
produire les correctifs : données structurées, pages de définition, présence
dans les sources que les IA citent réellement.

### ⬜ `site-publish` / `seo-fix` — appliquer sur le vrai site

**La seule pièce logicielle réellement défendable du projet.** Toutes les
librairies de skills produisent des *recommandations* ; aucune ne touche au site
du client, parce que ça demande des identifiants, des adaptateurs par
plateforme et une responsabilité. C'est exactement pour ça que c'est un fossé.

C'est aussi un poste d'heures récurrent : chaque contenu produit doit finir en
ligne. Conception retenue : un cœur commun (quoi faire) et des adaptateurs par
plateforme (comment l'appliquer).

| Plateforme | Voie d'accès | Difficulté |
| --- | --- | --- |
| WordPress | API REST + mot de passe d'application | faible |
| Shopify | Admin API | faible |
| HTML / statique | dépôt Git + pull request | faible |
| Webflow | API v2 | moyenne |
| Wix | API partenaire | moyenne |
| Squarespace | pas d'API d'écriture | ⚠ export de consignes manuelles |

Tout ce qui n'a pas d'API d'écriture retombe sur un livrable de consignes
précises. Dire « je ne peux pas, voilà exactement quoi faire » vaut mieux
qu'automatiser à l'aveugle.

### ⬜ `report` — ce qui a été fait, ce que ça a rapporté

**Priorité haute, et pas pour la raison qu'on croyait :** des rapports de
performance réguliers sont corrélés à une rétention supérieure de **38 %**
(étude sur ~200 k comptes PME, voir l'étude de marché). Ce n'est pas de
l'automatisation de confort, c'est le deuxième levier de rétention après le
nombre de produits.

Le reporting mensuel est aussi du temps non facturable pur. L'automatiser est de la
marge directe, et c'est aussi ce qui **fait progresser les chiffrages** : chaque
écart entre l'estimation annoncée et le réel corrige une hypothèse du prochain
`brand-core`.

### ⬜ `content-run` — l'enchaînement hebdomadaire

Orchestration, pas rédaction : prend les piliers et leur part de voix, appelle
les skills vendorisées pour produire, passe par `site-publish`, et s'arrête à la
validation humaine. C'est le poste d'heures le plus lourd du modèle parce qu'il
revient chaque semaine.

---

## Lot 2 — La couche française et locale

Ce que les librairies, toutes orientées SaaS anglophone, ignorent complètement.
C'est donc à nous, et c'est ce que la cible achète vraiment.

### ⬜ `gmb` — fiche Google Business

Catégories, description, attributs, photos, posts, réponses aux avis, alignés
sur la ligne éditoriale. Canal très rentable en local et presque toujours
négligé.

### ⬜ `local-seo`

Requêtes géolocalisées, pages par zone, annuaires et citations locales, données
structurées `LocalBusiness`.

### ⬜ `explain` — la couche pédagogique

« Pourquoi me conseilles-tu ça ? », « c'est quoi un CPC ? », dans le contexte de
la marque. Vulgariser est la fonctionnalité, pas la mise en forme.

---

## Lot 3 — Vendorisé, pas écrit

Ces capacités existent sous licence MIT, maintenues par des praticiens plus
crédibles et plus suivis que nous ne le serons (ADR-009). **Écrire nos versions
serait des semaines de travail pour un résultat inférieur.**

| ♻ Capacité | Statut |
| --- | --- |
| `seo-audit`, `ai-seo`, `schema`, `site-architecture`, `programmatic-seo` | à vendoriser |
| `competitors`, `content-strategy`, `copywriting`, `copy-editing` | à vendoriser |
| `ads`, `ad-creative`, `ab-testing`, `cro` | à vendoriser |
| `social` | à vendoriser |
| `cold-email`, `emails` | à vendoriser |
| `analytics`, `launch`, `pricing` | à vendoriser |

Procédure : `./scripts/vendor-skill.sh`, puis relecture avant activation
(ADR-004). Ces dépôts cumulent plus de mille commits et acceptent des
contributions externes : une mise à jour non relue change le comportement du
produit.

Deux réserves à garder en tête. Ces skills sont écrites pour le SaaS : tout ce
qui touche aux paywalls, à l'activation d'essai ou au PLG ne concerne pas la
cible. Et elles sont en anglais : les sorties destinées au client passent par
notre ligne éditoriale francophone.

### ⬜ `pretest` — pré-tester les créations

Variantes d'accroche et de visuel confrontées avant diffusion, avec l'écart au
brand-core mesuré. Écarte les ratés évidents ; ne prédit pas les succès, et
l'affiche (ADR-007).

### ⬜ `ai-marking` — signaler et marquer les contenus générés

Obligation en vigueur depuis le 2 août 2026 (article 50 de l'AI Act). Vit dans
le pipeline de publication, pas dans les CGV. Transverse à `site-publish` et
`social-publish` (ADR-011).

### ⬜ `coherence-check` — le gardien

Compare ce que racontent le site, les réseaux, la fiche Google et les annonces,
et signale les écarts à la ligne éditoriale. C'est l'outil qui rend la cohérence
vérifiable au lieu d'être déclarative — et le contrepoids nécessaire à des
skills externes qui, elles, ne connaissent que leur canal.

---

## Lot 4 — Bloqué par des accès, pas par du code

### 🔒 `social-publish`

| Réseau | Voie officielle | Ce qu'il faut |
| --- | --- | --- |
| Instagram / Facebook | Content Publishing API | app Meta, compte pro, Page liée, revue d'app |
| LinkedIn | Posts API | app LinkedIn, revue, partenariat selon le scope |
| TikTok | Content Posting API | app développeur, revue |
| X | API v2 payante | abonnement |
| Pinterest | API v5 | app, revue |

**L'automatisation non officielle est exclue** (ADR-006). Okara illustre le
risque : son auto-posting sur Reddit et Hacker News expose les comptes clients
à un ban pour spam. Un compte client fermé n'est pas un incident technique.

### 🔒 `ads-launch` / `ads-pilot`

Google Ads API et Meta Marketing API, avec plafond de dépense codé en dur et
validation humaine avant toute mise en ligne.

### ⬜ `prospect-find` / `prospect-enrich` / `sequence-write`

Le pont inbound/outbound est déjà dans le schéma : chaque ICP porte ses
`search_intents` (ce qu'on publie pour être trouvé) et son `where_to_find_them`
(où on va le chercher). Deux usages du même ciblage.

**Cadre légal à traiter dès la conception** : le RGPD encadre la prospection
B2B — base légale, mention d'information, droit d'opposition, conservation
limitée. L'outil journalise l'origine de chaque contact et permet une
suppression immédiate.

---


## Hors périmètre, assumé

- **Un CRM.** On s'y connecte, on n'en refait pas un.
- **Un éditeur de site.** On corrige des sites existants.
- **Un outil de design.** On génère des visuels publicitaires, pas une identité
  visuelle complète.
- **L'automatisation non officielle des réseaux.** Voir plus haut.
- **Une librairie de skills marketing.** Elles existent, MIT, mieux suivies
  (ADR-009). On les vendorise et on écrit le pont.
- **Descendre à 66 €/mois sans humain.** C'est le palier d'Okara, où la qualité
  se dégrade et où le client ne peut pas la juger. Le trou qu'on occupe est au
  dessus, et il n'y est que parce qu'un humain y répond (ADR-008).
- **Le conseil humain.** Agent Growth outille le consultant ; il ne le
  remplace pas. L'accompagnement humain reste une offre à part, et c'est ce qui
  justifie son prix.
