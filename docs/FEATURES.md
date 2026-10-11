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

## Les six règles de conception

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

## État d'avancement

| Statut | Signification |
| --- | --- |
| ✅ | Livré et testé |
| 🔜 | Prochain lot |
| ⬜ | Planifié |
| 🔒 | Bloqué par un accès externe (API, compte, contrat) |

---

## Socle — la ligne éditoriale

### ✅ `brand-core` — construire l'ADN de la marque

Lit le site de la marque et ceux de ses concurrents, puis produit :

- le positionnement et la catégorie dans laquelle le client la range ;
- les ICP (clients idéaux), avec pour chacun **ce qu'il tape sur Google**
  (matière du SEO) et **où il se trouve** (matière de l'outbound) ;
- l'analyse concurrentielle et l'espace laissé libre ;
- la ligne éditoriale : mission, promesse, preuves, curseurs de ton, vocabulaire
  à employer et à bannir, piliers de contenu avec leur part de voix, formats
  signature, interdits ;
- les angles différenciants, avec la preuve à réunir et le risque ;
- **6 à 10 opportunités chiffrées** par canal, classées par rentabilité ;
- les questions ouvertes — ce qui n'a pas pu être déduit et qu'il faut demander.

Produit trois fichiers : `brand-core.json` (le contrat), `brand-core.md` (le
document que le client lit) et `voice.md` (la fiche de voix que les outils de
rédaction consomment).

### 🔜 `brand-core refresh`

Relancer l'analyse sans perdre les corrections humaines : le client amende son
brand-core, ces amendements survivent au passage suivant.

---

## Lot 1 — Être trouvé (inbound)

C'est le lot prioritaire : c'est là que l'effet est le plus mécanique et le
moins dépendant d'un budget média.

### 🔜 `seo-audit`

Audit technique et sémantique, à partir de ce que le crawler lit déjà
(`ag inspect` en donne la base) : balises, structure, données structurées,
vitesse, maillage interne, pages orphelines, cannibalisation. Chaque constat est
traduit en « ce que ça vous coûte » plutôt qu'en score sur 100.

### 🔜 `seo-plan`

Transforme les `search_intents` des ICP en clusters de contenu : une page
pilier, ses pages satellites, l'intention derrière chacune, le volume estimé et
la difficulté. Chaque sujet est relié à un pilier éditorial — si un sujet ne
rentre dans aucun pilier, il n'est pas produit.

### ⬜ `seo-fix` — corriger directement sur le site

Le point techniquement le plus délicat du projet, et celui qui a le plus de
valeur : appliquer les corrections sur le site réel, quelle que soit la
plateforme. Conception retenue : un cœur commun (quoi corriger) et des
adaptateurs par plateforme (comment l'appliquer).

| Plateforme | Voie d'accès | Difficulté |
| --- | --- | --- |
| WordPress | API REST + mot de passe d'application | faible |
| Shopify | Admin API | faible |
| Webflow | API v2 | moyenne |
| Wix | API partenaire | moyenne |
| Squarespace | pas d'API d'écriture | ⚠ export de consignes manuelles |
| HTML / statique | dépôt Git + pull request | faible |

Tout ce qui n'a pas d'API d'écriture retombe sur un livrable de consignes
précises. Dire « je ne peux pas, voilà exactement quoi faire » vaut mieux
qu'automatiser à l'aveugle.

### ⬜ `geo-audit` — être cité par les IA

Interroger les assistants (ChatGPT, Claude, Perplexity, AI Overviews) sur les
requêtes de l'ICP, relever qui est cité et avec quelle formulation, puis
produire les correctifs : données structurées, pages de définition, présence
dans les sources que les IA citent réellement.

### ⬜ `gmb` — fiche Google Business

Aligner la fiche sur la ligne éditoriale : catégories, description, attributs,
photos, posts, réponses aux avis. Canal très rentable en local et presque
toujours négligé.

---

## Lot 2 — Publier (réseaux sociaux)

### ⬜ `social-plan`

Calendrier éditorial dérivé des piliers et de leur part de voix. Le calendrier
ne décide pas des sujets : il répartit les piliers dans le temps.

### ⬜ `social-write`

Rédaction par plateforme, en héritant de `voice.md`. **C'est ici qu'on branche
les skills de rédaction existantes** plutôt que de les réécrire — voir
[ARCHITECTURE.md](ARCHITECTURE.md#brancher-une-skill-externe) et la décision
[ADR-004](DECISIONS.md#adr-004--réutiliser-les-skills-de-rédaction-existantes).

### ⬜ `pretest` — pré-tester les créations

Avant diffusion : plusieurs variantes d'accroche et de visuel, confrontées entre
elles sur l'attention probable et la justesse de ton, avec l'écart au brand-core
mesuré. Ce n'est pas une boule de cristal : l'objectif est d'écarter les ratés
évidents, pas de prédire un succès. L'outil affiche donc ce qu'il sait faire et
ce qu'il ne sait pas faire.

### 🔒 `social-publish`

Publication effective. Le blocage n'est pas technique mais contractuel :

| Réseau | Voie officielle | Ce qu'il faut |
| --- | --- | --- |
| Instagram / Facebook | Content Publishing API | app Meta, compte pro, Page liée, revue d'app |
| LinkedIn | Posts API | app LinkedIn, revue, partenariat selon le scope |
| TikTok | Content Posting API | app développeur, revue |
| X | API v2 payante | abonnement |
| Pinterest | API v5 | app, revue |

**L'automatisation non officielle est exclue** : publier, commenter, suivre ou
envoyer des messages via un navigateur piloté viole les conditions
d'utilisation d'Instagram et de LinkedIn, et fait fermer les comptes clients.
Un compte client fermé est une faute professionnelle, pas un incident
technique. Tant que l'accès officiel n'est pas en place, l'outil prépare le post
et le remet à valider — ce qui est déjà l'essentiel du travail.

---

## Lot 3 — Payer (publicité)

### ⬜ `ads-plan`

Mots-clés et audiences dérivés des ICP, structure de campagne, budget conseillé
et estimations chiffrées (CPC, volume, coût par lead attendu) avec leurs
hypothèses.

### ⬜ `ads-create`

Textes d'annonces et visuels, en variantes destinées au pré-test, conformes à la
ligne éditoriale et aux interdits (`do_not_say`).

### 🔒 `ads-launch` / `ads-pilot`

Lancement et pilotage. Google Ads API et Meta Marketing API, avec plafond de
dépense codé en dur et validation humaine obligatoire avant toute mise en ligne.
Un agent qui dépense de l'argent sans porte de validation est un risque, pas une
fonctionnalité.

---

## Lot 4 — Aller chercher (outbound)

Le pont avec l'inbound est déjà posé dans `brand-core` : un ICP y porte à la
fois ses `search_intents` (ce qu'on publie pour être trouvé) et son
`where_to_find_them` (où on va le chercher). Deux usages du même ciblage.

### ⬜ `prospect-find`

Constituer une liste à partir de `where_to_find_them` : annuaires, sources
publiques, critères de filtrage. **Cadre légal à traiter dès la conception, pas
après** : en Europe, le RGPD encadre la prospection B2B — base légale, mention
d'information, droit d'opposition, conservation limitée. L'outil doit journaliser
l'origine de chaque contact et permettre une suppression immédiate.

### ⬜ `prospect-enrich`

Enrichissement et qualification contre l'ICP, avec un score et sa justification.

### ⬜ `sequence-write`

Séquences personnalisées écrites dans la ligne éditoriale. Un e-mail de
prospection qui ne sonne pas comme la marque abîme la marque.

---

## Transverse

### ⬜ `coherence-check` — le gardien

Compare ce que racontent le site, les réseaux, la fiche Google et les annonces,
et signale les écarts à la ligne éditoriale. C'est l'outil qui rend la promesse
de cohérence vérifiable au lieu d'être déclarative.

### ⬜ `report` — ce qui a été fait, ce que ça a rapporté

Journal des actions et résultats mesurés, avec la comparaison entre
l'estimation annoncée et le réel. **Cette boucle est ce qui fait progresser les
estimations** : chaque écart constaté corrige les hypothèses du prochain
chiffrage.

### ⬜ `explain` — la couche pédagogique

« Pourquoi me conseilles-tu ça ? », « c'est quoi un CPC ? », à tout moment et
dans le contexte de la marque.

---

## Hors périmètre, assumé

- **Un CRM.** On s'y connecte, on n'en refait pas un.
- **Un éditeur de site.** On corrige des sites existants.
- **Un outil de design.** On génère des visuels publicitaires, pas une identité
  visuelle complète.
- **L'automatisation non officielle des réseaux.** Voir plus haut.
- **Le conseil humain.** Agent Growth outille le consultant ; il ne le
  remplace pas. L'accompagnement humain reste une offre à part, et c'est ce qui
  justifie son prix.
