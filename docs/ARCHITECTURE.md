# Architecture

Objectif affiché : **l'infrastructure la plus simple possible**. Ce document dit
ce qu'on construit, ce qu'on refuse de construire, et comment brancher les
dépôts GitHub déjà accumulés.

## La forme générale

```
Agent-Growth/
├── src/agent_growth/          le code : outils, schéma, rendu, CLI
│   ├── schemas.py             le contrat brand-core (source de vérité)
│   ├── crawl.py               lecture des sites
│   ├── llm.py                 unique point d'accès à Claude
│   ├── render.py              JSON → documents lisibles
│   └── tools/                 un fichier par outil
├── skills/                    les mêmes capacités, exposées à Claude
│   ├── brand-core/SKILL.md
│   └── vendor/                skills externes, copiées et épinglées
├── brands/<marque>/           l'espace de travail d'une marque
│   ├── brand-core.json        le contrat
│   ├── brand-core.md          ce que le client lit
│   └── voice.md               ce que les outils de rédaction lisent
└── docs/
```

Trois idées suffisent à tenir l'ensemble.

### 1. L'état tient dans des fichiers

Un dossier par marque. Pas de base de données, pas de serveur, pas de file
d'attente. On peut lire, corriger à la main, versionner, envoyer au client,
diffuser à une équipe. Le jour où un dossier de fichiers ne suffit plus, on
aura un vrai usage pour décider quoi mettre à la place — pas une intuition.

### 2. Un outil = une fonction Python + une skill

Chaque capacité existe sous deux formes, à partir du même code :

- **une commande** (`ag brand-core https://…`), pour scripter, planifier,
  rejouer ;
- **une skill** (`skills/brand-core/SKILL.md`), pour que Claude l'utilise en
  conversation, en sachant quand et comment.

Le `SKILL.md` ne contient pas de logique : il explique quand lancer l'outil et
quoi faire du résultat. Un seul endroit à corriger quand la logique change.

### 3. Le `brand-core.json` est le seul couplage autorisé

Les outils ne s'appellent pas entre eux. Ils lisent et écrivent des fichiers du
dossier de la marque. `seo-plan` lit `brand-core.json` ; il n'appelle jamais
`brand-core`. Conséquence pratique : on peut ajouter, remplacer ou supprimer un
outil sans toucher aux autres.

## Pourquoi Python

- Le terrain (crawl, SEO, données, scraping outbound) y est le mieux outillé.
- Les skills de contenu déjà disponibles sur GitHub sont en Python — les
  réutiliser ne demande aucune traduction.
- Le SDK Anthropic officiel y est de première classe.

Une interface web viendra peut-être en TypeScript par-dessus les mêmes fichiers.
Ce sera une vue, pas un second cerveau.

## Pourquoi pas…

| Option | Pourquoi non |
| --- | --- |
| **n8n / Make / Zapier** | Une ligne éditoriale ne tient pas dans un schéma de flux. Le jour où il faut expliquer *pourquoi* un angle a été retenu, un graphe de nœuds ne sait pas répondre. |
| **Un framework d'agents** (LangGraph, CrewAI…) | On y gagnerait une abstraction et on y perdrait la lisibilité. Les outils ici sont séquentiels : lire, analyser, écrire. Une fonction suffit. |
| **Une base de données** | Voir plus haut. Elle viendra quand un usage l'exigera. |
| **Un agent unique qui fait tout** | Impossible à déboguer et impossible à vendre. Un client achète « l'audit », « le calendrier », « les campagnes » — pas « l'agent ». |

## Le modèle

Un seul endroit décide : `src/agent_growth/llm.py`.

- Modèle par défaut `claude-opus-5-5`, surchargeable par `AG_MODEL`.
- **Structured outputs** : on demande un schéma Pydantic et on reçoit un objet
  validé. Pas de JSON à parser à la main, pas de champ manquant qui casse trois
  outils plus loin.
- `effort: "high"` : l'analyse stratégique en vaut le coût ; le défaut du modèle
  (`medium`) est trop bas pour ça.
- Si le modèle décline une demande, un modèle de repli est tenté une fois avant
  d'abandonner — un outil qui s'arrête sans explication coûte plus cher qu'une
  ligne de code.

## Brancher une skill externe

C'est la réponse à « connecter mes différents GitHub ».

### La règle : copier et épingler, ne pas dépendre

Un sous-module Git fait entrer du code tierce-partie qui **change sous vos
pieds**. Une skill, c'est des instructions que Claude suit et des scripts qu'il
exécute : une modification en amont modifie le comportement de votre produit
sans que vous l'ayez décidée. On copie donc, on note d'où ça vient, et on met à
jour quand on l'a choisi.

```bash
./scripts/vendor-skill.sh https://github.com/auteur/depot-skill ig
```

Le script copie les dossiers de skills dans `skills/vendor/<nom>/` et y écrit un
`VENDOR.md` qui enregistre l'origine, le commit exact, la licence et la date.

### À lire avant d'activer, sans exception

Une skill externe est du code et des instructions que Claude va suivre. Avant
de l'activer :

1. **Lire chaque `SKILL.md`.** Y cherche-t-on à lire des fichiers hors du
   projet, à appeler le réseau, à contourner une validation ?
2. **Lire chaque script.** Appels réseau, accès disque, dépendances.
3. **Vérifier la licence.** MIT et Apache-2.0 permettent l'usage commercial.
4. **Vérifier ce que la skill prétend faire.** Un auteur honnête documente ses
   limites ; lisez-les et ne présentez pas ses scores comme des vérités.

### Ce qu'une skill de rédaction apporte — et ce qu'elle n'apporte pas

| Apporte | N'apporte pas |
| --- | --- |
| Le savoir-faire rédactionnel d'un réseau (formats d'accroche, longueurs, codes) | La connaissance de **votre** marque — c'est le rôle de `voice.md` |
| Des scripts d'aide locaux et sans dépendance | La publication effective — il faut les API officielles |
| Un gain de temps réel sur la création | La stratégie, le chiffrage, la mesure |

Autrement dit : une skill externe fait gagner **la couche création**. Elle ne
fait pas gagner l'agent. Détail du raisonnement dans
[ADR-004](DECISIONS.md#adr-004--réutiliser-les-skills-de-rédaction-existantes).

### Comment une skill externe hérite de la marque

Les skills de rédaction attendent conventionnellement un fichier de voix
(`templates/voice.md`). `brand-core` produit exactement ce fichier. Les brancher
tient donc en une ligne :

```bash
cp brands/ma-marque/voice.md skills/vendor/ig/templates/voice.md
```

Ce fichier est de la prose lue par le modèle, pas un format à champs : la
correspondance avec les sections attendues en amont est sémantique, pas
littérale. Inutile d'en calquer les intitulés.

C'est pour ça que `brand-core` est le premier outil : il rend toutes les skills
de rédaction immédiatement spécifiques à la marque, sans saisie manuelle.

## La plateforme, plus tard

« Une plateforme où tout est géré » est la bonne cible finale, et le mauvais
point de départ : une interface sans outils derrière n'est qu'une maquette.
L'ordre retenu :

1. **Les outils en ligne de commande** — on peut les vendre en prestation dès
   maintenant, et chaque mission dit lesquels valent vraiment quelque chose.
2. **Les skills** — Claude les enchaîne en conversation, le client voit le
   produit sans interface à construire.
3. **L'interface web** — quand on saura, par l'usage, quels écrans existent
   vraiment. Elle lira les mêmes fichiers.

## Secrets

Jamais dans le dépôt. Variables d'environnement, `.env` ignoré par Git (voir
`.env.example`). `brands/` est également ignoré : les données clients ne partent
pas sur GitHub par accident.
