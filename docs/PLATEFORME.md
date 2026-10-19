# La plateforme — ce qu'on construit vraiment

*13 octobre 2026. Ce document remplace la lecture « par canal » de
[FEATURES.md](FEATURES.md) comme feuille de route. Les canaux (SEO, GEO, social,
ads) sont des **modules de la console**, pas le produit.*

## Correction de cadrage

Le produit n'est pas un outil SEO. C'est **une console qui pilote tout le
marketing digital de plusieurs marques à la fois**, avec :

- une **ligne éditoriale par marque**, qui commande tout le reste ;
- du **contenu organique produit chaque jour**, programmé, conforme à cette ligne ;
- de la **publicité générée et pilotée automatiquement** ;
- des **résultats remontés de tous les canaux**, au même endroit ;
- du **reporting automatique**, et une analyse qui boucle sur ce qu'on produit ensuite ;
- un **accès client en lecture**, pour les marques qui veulent suivre elles-mêmes.

Le SEO et le GEO sont deux canaux parmi huit. Ils gardent leur intérêt
(l'étude de marché montre que le GEO est le mieux payé), mais ils ne sont pas
la colonne du produit.

**Premier objectif : l'outil parfait pour une seule personne**, qui gère ses
propres marques. La structure multi-marques est posée dès le premier jour parce
qu'elle ne coûte presque rien à ce moment-là, et qu'elle est ce qui rend le
produit vendable ensuite.

## Le modèle de données

Tout tient dans cinq objets. C'est ce qui permet d'ajouter une marque, un canal
ou un module sans rien casser.

```
Espace de travail (toi)
└── Marque  ────────────────  Egyptours, Oria, client X…
    ├── brand-core.json        la ligne éditoriale (déjà construit)
    ├── Site(s)                plateforme, pages, accès d'écriture
    ├── Canal                  IG, LinkedIn, Google Ads, Meta Ads, fiche Google, e-mail…
    │   └── Compte connecté    jetons OAuth, identifiants de compte
    ├── Contenu                prévu → généré → validé → publié → mesuré
    ├── Campagne               budget, plafond, créations, état
    └── Mesure                 (canal, métrique, date, valeur) — série temporelle
```

**Une seule table porte toute l'intelligence de reporting** : `Mesure`, en
`(marque, canal, métrique, date, valeur)`. Tous les tableaux de bord, toutes les
comparaisons entre marques et tous les rapports se calculent dessus. C'est le
choix qui évite d'avoir un écran spécifique par plateforme.

**Conséquence : il faut une base de données.** Des fichiers suffisaient pour une
analyse de marque ; ils ne suffisent pas pour des séries temporelles
multi-marques, des jetons OAuth à rafraîchir et des tâches planifiées. Ce point
amende [ADR-003](DECISIONS.md#adr-003--des-fichiers-pas-de-base-de-données) —
voir [ADR-012](DECISIONS.md#adr-012--le-produit-est-la-console-multi-marques-pas-un-canal).

## Les six modules

| Module | Ce qu'il fait | Dépend de |
| --- | --- | --- |
| **1. Marque** | La ligne éditoriale, les ICP, les angles, les opportunités chiffrées | ✅ construit (`brand-core`) |
| **2. Collecte** | Remonte chaque nuit les chiffres de tous les canaux dans `Mesure` | OAuth par plateforme |
| **3. Console** | Vue portefeuille (toutes les marques), vue marque, vue canal | module 2 |
| **4. Contenu** | Calendrier dérivé des piliers, **surproduction puis sélection par pré-test**, file de validation, publication | modules 1 et 2 |
| **5. Publicité** | Créations en variantes, lancement, pilotage sous plafond de dépense | modules 1 et 2 |
| **6. Rapport** | Rapport automatique par marque, écart entre estimation annoncée et réel | modules 2 et 3 |
| **7. Prospection** | Sourcing, enrichissement, séquences personnalisées dans la voix de la marque | modules 1 et 2 |

L'ordre n'est pas un goût : **2 avant 3 avant 4 et 5**. Sans collecte, la console
est vide ; sans console, on produit à l'aveugle.

## Lire est facile, écrire est gardé

C'est le fait qui structure tout le calendrier. Les plateformes laissent lire
sans difficulté, mais filtrent l'écriture — et surtout l'écriture **pour le
compte d'autrui**.

### Pour tes propres marques

| Accès | Ce qu'il faut | Délai |
| --- | --- | --- |
| Analytics GA4, Search Console | OAuth sur ton propre compte | immédiat |
| **Google Ads** (lecture et écriture) | Les *developer tokens* ont été **supprimés le 9 septembre 2026**. L'accès est désormais attaché au projet Google Cloud : vérification de marque du projet, puis l'accès « Basic » est accordé **automatiquement en quelques minutes** | heures |
| Meta — statistiques IG et Facebook | App Meta en mode développement, ton compte en rôle testeur | immédiat |
| **Meta Ads** (lecture et écriture) | Jeton d'utilisateur système sur tes propres comptes publicitaires — **aucune revue d'app** | immédiat |
| Publication Instagram | `instagram_business_basic` + `instagram_business_content_publish`, compte professionnel, mode développement | immédiat |
| **Fiche Google Business** | Formulaire « Application For Basic API Access ». Un quota à 0 signifie non accordé. Revue **manuelle** | **~14 jours** |

**Conclusion décisive : pour Egyptours et Oria, tu n'as presque aucune revue
d'app à passer.** Seule la fiche Google Business demande d'attendre. Tout le
reste est accessible en quelques heures.

### Pour les comptes de clients

C'est là que les portes se ferment.

| Accès | Ce qu'il faut | Délai |
| --- | --- | --- |
| Publication Instagram pour autrui | **Advanced Access**, revue d'app **par permission**, avec vidéo de démonstration du parcours complet | 2 à 4 semaines par soumission |
| Meta Ads pour autrui | **Advanced Access** + **vérification d'entreprise** (documents légaux) | quelques jours à quelques semaines |
| Google Ads, accès « Standard » | Audit **manuel** | variable |
| LinkedIn, TikTok | Programmes partenaires, plus restrictifs | long |

**Donc l'ordre de construction s'impose de lui-même** : la phase 1 ne demande
aucune revue, et les revues de la phase 4 se lancent **en parallèle** du
développement, pas après.

*Ces règles changent souvent et les sources sont majoritairement des guides
tiers. À revérifier dans la documentation officielle au moment de brancher
chaque plateforme.*

## L'ordre de construction, et le temps

Estimations en **jours de travail effectif** — pas en jours de calendrier.

### Phase 1 — La console en lecture *(aucune revue d'app)*

| Tâche | Jours |
| --- | --- |
| Base de données multi-marques, authentification, registre des marques | 4 |
| Coquille de la console : sélecteur de marque, vue portefeuille | 5 |
| Connecteur GA4 + Search Console | 3 |
| Connecteur Meta (statistiques IG et Facebook) | 4 |
| Connecteur Google Ads (lecture) | 3 |
| Connecteur fiche Google Business (lecture) | 3 |
| Collecte planifiée chaque nuit + historisation | 3 |
| Rapport automatique par marque | 4 |
| **Total** | **29 jours** |

**À la fin de la phase 1, tu pilotes Egyptours et Oria depuis un seul écran, et
tu reçois un rapport automatique.** C'est déjà l'essentiel de ce que tu
demandes.

### Phase 2 — Le contenu organique

Produire beaucoup pour publier peu (ADR-014) : le taux de rejet est un
indicateur de qualité, pas un gâchis.

| Tâche | Jours |
| --- | --- |
| Calendrier dérivé des piliers et de leur part de voix | 4 |
| Génération quotidienne par canal + pré-test + file de validation | 6 |
| Génération des visuels (API image et vidéo) | 4 |
| Publication sur tes propres comptes | 4 |
| Signalement et marquage IA Act | 2 |
| **Total** | **20 jours** |

### Phase 3 — La publicité automatisée

| Tâche | Jours |
| --- | --- |
| Génération des créations en variantes (textes + visuels) | 5 |
| Lecture des performances et attribution | 4 |
| Écriture : création et mise en pause de campagnes, sous plafond **codé en dur** | 8 |
| Boucle d'analyse → recommandations chiffrées | 5 |
| **Total** | **22 jours** |

### Phase 4 — Ouvrir à des clients

| Tâche | Jours |
| --- | --- |
| Cloisonnement multi-locataires propre + accès client en lecture | 6 |
| Facturation et abonnements | 4 |
| Dossiers de revue Meta + vérification d'entreprise | 3 *(+ 2 à 6 semaines d'attente)* |
| Démarrage autonome d'une nouvelle marque | 5 |
| **Total** | **18 jours + attente** |

### Traduction en calendrier

| | Jours de travail | À plein temps | À mi-temps |
| --- | --- | --- | --- |
| Phase 1 | 29 | **~6 semaines** | ~3 mois |
| Phases 1+2 | 49 | ~10 semaines | ~5 mois |
| Phases 1+2+3 | 71 | ~14 semaines | ~7 mois |
| Tout | 89 | **~18 semaines** | ~9 mois |

Deux réserves honnêtes. Les connecteurs sont du travail d'intégration : les
API ont des bizarreries que l'IA n'accélère pas beaucoup, et il faut compter
une marge de 30 % sur ces lignes-là. Et les revues d'app de la phase 4 sont du
temps de calendrier qu'on ne compresse pas — à lancer en parallèle de la phase 3.

## Combien, seul

### Les coûts par marque

| Poste | Par marque et par mois |
| --- | --- |
| Modèle de langage (contenu quotidien, analyses) | 15 à 40 € |
| Génération d'images et de vidéos | 10 à 80 € selon le volume |
| Hébergement et base (mutualisé, pas par marque) | 20 à 60 € au total |
| **Coût marginal d'une marque** | **30 à 120 €/mois** |

Sur un panier à 1 500 €/mois, la marge brute est de **l'ordre de 90 %**. Le coût
qui compte n'est pas l'infrastructure, c'est le temps humain.

### La montée en charge

*Hypothèses : panier moyen 1 500 €/mois, 1 h 30 de travail humain par client et
par mois après le démarrage, 2 à 3 nouveaux clients par mois une fois la
machine en route.*

| | Clients | Revenu mensuel | Chiffre d'affaires annuel | Heures/mois |
| --- | --- | --- | --- | --- |
| **Année 1** | 10 à 15 en fin d'année | 15 à 22 k€ | **70 à 110 k€** | ~20 h |
| **Année 2** | 30 à 35 | 45 à 52 k€ | **450 à 550 k€** | ~50 h |
| **Année 3, plafond solo** | 35 à 40 | 52 à 60 k€ | **550 à 700 k€** | ~60 h |

L'année 1 est basse parce que les 4 à 6 premiers mois servent à construire :
l'acquisition ne démarre vraiment qu'au mois 5 ou 6.

**Le plafond solo se situe autour de 35 à 40 clients.** Pas à cause de la
livraison — la plateforme la réduit — mais à cause de la **prospection et du
support**, qui ne s'automatisent pas au même rythme.

**Et la vraie contrainte n'est pas la livraison, c'est de trouver les clients.**
Toute la plateforme sert à faire tenir 35 clients dans un agenda. Elle ne sert
à rien si on n'en a que trois.

## Comment ça scale au-delà de soi

Trois chemins, du plus fort levier au plus faible. Les trois exigent la
plateforme — c'est pour ça que la construire est juste.

### 1. Vendre la plateforme à d'autres agences *(le meilleur levier)*

Ce sont elles qui apportent les clients ; tu fournis l'outil.
**100 agences à 300 €/mois = 30 000 €/mois, sans aucune livraison client.**
C'est exactement le modèle de GoHighLevel, et l'étude de marché montre qu'il
y a de l'argent. Accessible seulement après avoir prouvé la plateforme sur de
vrais clients.

### 2. Le palier bas en autonomie complète

La plateforme fait son propre démarrage, le client n'a jamais d'humain en face.
Panier faible, mais aucune heure consommée. C'est le palier que Wix et Shopify
menacent — donc à traiter comme une porte d'entrée vers le palier supérieur.

### 3. Recruter sur la livraison

Un chargé de compte gère 25 à 30 clients avec la plateforme. Croissance
linéaire, prévisible, sans levier — mais fiable, et ça ne demande aucune
nouvelle technologie.

## Ce qui peut faire échouer

Dans l'ordre de probabilité, pas de gravité.

1. **Construire 4 mois sans vendre.** Le risque principal, et de loin. La phase 1
   doit servir Egyptours et Oria pour de vrai, pas être un prototype.
2. **Les connecteurs prennent deux fois plus longtemps que prévu.** C'est la
   norme en intégration d'API. D'où la marge de 30 %.
3. **Dépenser de l'argent sans garde-fou.** La publicité automatisée est la seule
   partie où un bug coûte directement de l'argent au client. Plafond codé en
   dur, validation humaine avant la première mise en ligne, journal de toutes
   les décisions.
4. **Faire fermer un compte client.** Pas d'automatisation non officielle,
   jamais ([ADR-006](DECISIONS.md#adr-006--pas-dautomatisation-non-officielle-des-réseaux)).
5. **Une plateforme change ses règles d'accès.** C'est déjà arrivé deux fois en
   2026 (Google Ads en septembre, les permissions Instagram en janvier 2025).
   Un connecteur par fichier, isolé derrière une interface commune, pour qu'une
   rupture n'en casse qu'un.

## Avancement

| | État |
| --- | --- |
| Module 1 — Ligne éditoriale (`brand-core`) | ✅ construit, testé |
| **Le socle de la console** : base multi-marques, 13 tables, migrations | ✅ construit, testé |
| **Registre des marques, sites, canaux** | ✅ `ag brand add`, `ag import-core` |
| **Registre des outils branchables** (37 outils, 9 catégories) | ✅ `ag tools`, `ag connect` |
| **Les écrans** : portefeuille, fiche marque, outils | ✅ `ag serve` |
| **Modèle de prospection** : prospects, séquences, envois, RGPD dans le schéma | ✅ construit, testé |
| **Autonomie** : file de validation, validation automatique plafonnée, planificateur 24/7 | ✅ construit, testé |
| **Telegram** : validation en un geste, seul le propriétaire décide | ✅ construit, testé |
| **Adaptateurs de sites** : WordPress, Shopify, sur mesure (GitHub), manuel (SpeedMedia…) | ✅ construit, testé |
| **Mise en ligne** : Railway, mot de passe obligatoire, volume persistant | ✅ prêt — [DEPLOIEMENT.md](DEPLOIEMENT.md) |
| **Audit SEO / GEO présentable au client** : 3 piliers, vitesse, E-E-A-T, sémantique, rapport HTML/PDF | ✅ construit, testé — `ag audit`, ADR-016 |
| **Mots-clés et concurrents** (DataForSEO, logique d'OpenSEO) | ✅ construit, testé — attend la clé `DATAFORSEO_API_KEY` |
| **Charte graphique de l'outil** (DA) : couleurs, typographie, logo, ton visuel | ⬜ **à définir avec Lovable** — préalable à l'interface |
| **L'interface** : espace consultant + espace client, agent intégré, validations | ⬜ à construire sur la charte (remplace la console Jinja et Telegram) |
| Module 2 — Collecte (les connecteurs) | 🔜 le prochain chantier |
| Modules 3 à 7 | ⬜ |

Ce qui tourne déjà :

```bash
ag brand add https://egyptours.fr --channel instagram --channel google_ads --platform wordpress
ag brand-core https://egyptours.fr          # la ligne éditoriale
ag import-core brands/egyptours-fr/brand-core.json
ag tools                                     # les 37 outils et leur mode d'accès
ag connect ga4 GOOGLE_OAUTH_REFRESH          # une référence, jamais un secret
ag serve                                     # la console sur http://127.0.0.1:8000
```

## Pistes repérées, à intégrer

- **Création vidéo par MCP.** Higgsfield expose un serveur MCP officiel
  (`mcp.higgsfield.ai/mcp`, depuis le 30 avril 2026) et une compétence
  « Katana » qui refait un montage de référence avec les visuels de la marque.
  À brancher plutôt qu'à reconstruire (ADR-009). Le nom « Claude Motion » n'est
  attesté que par les supports de Higgsfield : à vérifier avant d'en dépendre.
- **Veille des annonces gagnantes.** Une annonce qui tourne depuis longtemps est
  une annonce qui rapporte : l'annonceur coupe les perdantes. C'est un signal de
  pré-test gratuit et public. La bibliothèque publicitaire de Meta expose par
  API toutes les annonces diffusées dans l'UE (article 39 du DSA) — à confirmer
  dans la documentation officielle avant de construire dessus.

### Notées par le fondateur le 2026-10-19, pour plus tard

- **La charte de l'outil, faite avec Lovable.** Des couleurs qui donnent envie,
  une UX ultra efficace et facile à comprendre — la cible est un dirigeant
  sans formation marketing (CLAUDE.md). Le connecteur Lovable est disponible
  depuis les sessions de travail : on peut générer les maquettes de là.
- **Google Ads et Meta Ads par MCP.** Repéré :
  `github.com/irinabuht12-oss/google-ads-meta-ads-mcp`. Vérifié le 2026-10-19 :
  le dépôt ne contient **aucun code** — seulement de la documentation et des
  fichiers de configuration qui pointent vers un serveur hébergé payant (Ryze,
  89 $/mois d'après leur propre tableau). La licence MIT ne couvre donc rien de
  réutilisable. Leur tableau cite deux alternatives à vérifier avant de choisir :
  le MCP officiel de Google (`github.com/googleads/google-ads-mcp`, lecture
  seule, gratuit) et celui de Meta (hébergé par Meta). Les écritures passeront
  de toute façon par notre file de validation (règle 3).
- **Higgsfield par MCP** pour la vidéo (voir plus haut).
- **TikTok Ads, X Ads** : à connecter aussi, par API officielles uniquement
  (règle 4).
- **Diffusion et récupération** : brancher les API de chaque canal dans les deux
  sens — publier (après validation) et rapatrier les résultats pour la mesure.

## La prochaine chose à faire

1. **La charte graphique de l'outil.** Les rapports d'audit sont déjà
   construits pour la recevoir : toutes leurs couleurs et polices sont des
   variables en tête de `templates/audit_report.html`. La même charte servira
   l'interface.
2. **L'interface** consultant + client, sur cette charte : audits, validations
   (le client valide ses contenus, le consultant les dépenses), agent intégré.
3. **Brancher les clés** des audits : `PAGESPEED_API_KEY` (gratuite) et
   `DATAFORSEO_API_KEY` (à l'usage) — voir [DEPLOIEMENT.md](DEPLOIEMENT.md).
