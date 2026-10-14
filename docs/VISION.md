# Vision — pourquoi ce système peut battre des acteurs beaucoup plus gros

*Écrit à la demande explicite de ne pas brider l'ambition. Ce document décrit
l'état final visé et le mécanisme qui le rend atteignable. Ce n'est pas une
feuille de route : elle est dans [PLATEFORME.md](PLATEFORME.md).*

## Les trois catégories qui existent aujourd'hui

| Catégorie | Qui | Ce qu'on achète | Qui fait le travail |
| --- | --- | --- | --- |
| **Outils qu'un humain pilote** | GoHighLevel, HubSpot, Vendasta, Semrush | Des tunnels, un CRM, des automatisations à configurer | **L'humain.** Il décide quoi publier, construit le tunnel, écrit l'annonce. |
| **Agents qui rédigent** | Okara, Collision, Jasper | Des brouillons sur demande | **L'humain.** Il publie, mesure, décide. |
| **Agences humaines** | les agences classiques | Du temps de spécialiste | L'agence, à la main, cher. |

Chacune laisse la décision et l'exécution à un humain. C'est le trou, et il
n'est pas un trou de fonctionnalité : c'est un trou de **catégorie**.

## La catégorie qu'on vise

**Un opérateur marketing autonome.** Une seule entrée — la ligne éditoriale de
la marque — et tout le reste est produit, publié, mesuré et corrigé sans
intervention, sauf aux portes de validation qu'on garde volontairement.

```
              ┌──────────────────────────────┐
     ENTRÉE   │   La ligne éditoriale        │  ← construite depuis le site,
              │   (positionnement, ICP,      │    les concurrents, les documents
              │    piliers, ton, interdits)  │
              └──────────────┬───────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   ┌─────────┐         ┌──────────┐         ┌───────────┐
   │ Contenu │         │   Pubs   │         │ Prospects │
   │ chaque  │         │ créées,  │         │ trouvés,  │
   │  jour   │         │ lancées, │         │ enrichis, │
   │ 8 canaux│         │ pilotées │         │ séquencés │
   └────┬────┘         └────┬─────┘         └─────┬─────┘
        │   ⚠ validation    │  ⚠ plafond          │  ⚠ RGPD
        └───────────────┬───┴─────────────────────┘
                        ▼
              ┌──────────────────┐
              │ Tout est mesuré  │  chaque nuit, tous les canaux
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │ La ligne se      │  ← LA BOUCLE. Personne ne la ferme.
              │ corrige elle-même│
              └────────┬─────────┘
                       │
                       └──────────► retour à l'entrée, en mieux
```

Les trois ⚠ ne sont pas des limites techniques qu'on lèvera plus tard. Ce sont
des choix : publier, dépenser et contacter sont les trois actions où une erreur
abîme le client. Elles gardent une porte.

## Pourquoi les gros ne peuvent pas simplement copier

Ce n'est pas une question d'avance, c'est une question de structure. Quatre
raisons, dans l'ordre de solidité.

### 1. Leur modèle de données n'a pas de place pour une ligne éditoriale

Le modèle de HubSpot, c'est des contacts et des affaires. Celui de GoHighLevel,
des tunnels et des pipelines. Aucun des deux n'a d'objet « ce que cette marque a
le droit de dire, et avec quels mots ». L'ajouter n'est pas une fonctionnalité :
c'est réécrire le cœur, et tout ce qui est branché dessus.

Nous, on part de là. C'est la seule chose qu'on ait construite en premier, et ce
n'était pas un hasard.

### 2. Une plateforme ne sert que ses propres clients

Shopify ne corrigera jamais un site Webflow. Wix n'optimisera jamais une fiche
Google qui envoie vers un concurrent de Wix. HubSpot optimise ce qui se passe
dans HubSpot. **C'est une impossibilité de leur modèle économique, pas un retard
de leur feuille de route** — et c'est précisément ce qui laisse la place à
quelqu'un qui n'appartient à aucun camp.

Une marque réelle est sur un site WordPress, une fiche Google, Instagram,
Google Ads et une boîte mail. Personne à l'intérieur d'un mur ne voit cet
ensemble.

### 3. Leur étendue est leur fossé et leur prison

250 intégrations, c'est 250 choses à maintenir, et chacune au minimum
fonctionnel. Un système qui traite **huit canaux de bout en bout** — produire,
publier, mesurer, corriger — bat 250 canaux à moitié branchés, parce que le
client n'achète pas le nombre de cases, il achète un résultat.

### 4. Personne ne ferme la boucle

C'est le point le plus important du document.

Tout le monde produit. Certains mesurent. **Personne ne reboucle la mesure sur
la décision suivante.** Le rapport mensuel part au client et meurt là.

Chez nous, un écart entre l'estimation annoncée et le réel n'est pas une gêne,
c'est une donnée : il corrige l'hypothèse qui a servi à la produire. C'est pour
ça que le schéma impose depuis le premier jour qu'une estimation porte ses
hypothèses et son origine. Ce n'était pas de la rigueur décorative, c'était
l'amorce de la boucle.

## Le vrai fossé, à terme : le jeu de données

Ce qui se construit tout seul, chaque jour, pour chaque marque :

```
(ligne éditoriale) → (action produite) → (résultat mesuré)
```

Personne d'autre ne peut l'avoir, parce qu'il faut les trois au même endroit.
Les outils ont l'action. Les agences ont le résultat, dans des tableurs. Les
agents qui rédigent n'ont ni l'un ni l'autre après la publication.

Et ça **compose** :

| | Ce que le système sait |
| --- | --- |
| 1 marque, 3 mois | ce qui marche pour cette marque |
| 10 marques d'un même métier, 1 an | ce qui marche pour ce métier — un nouveau client démarre avec la réponse |
| 100 marques, 10 métiers, 2 ans | quel angle, quel format, quel canal et quel budget pour un profil donné, avec les chiffres réels |

À ce stade, la question du client n'est plus « est-ce que votre IA écrit bien »
mais « combien ça va me rapporter » — et c'est la seule question dont on a la
réponse mesurée.

**C'est ça qui tient face à une entreprise qui a cent fois plus d'ingénieurs :
elle peut copier le logiciel en un trimestre, elle ne peut pas copier deux ans
de boucle fermée.**

## L'état final, concrètement

Ce que le système fait sans qu'on le lui demande :

- **Chaque nuit** : relève tous les canaux de toutes les marques, détecte les
  anomalies, prépare ce qui doit sortir demain.
- **Chaque jour** : produit le contenu du calendrier, en variantes pré-testées,
  et le présente à valider. Ce qui est validé part, marqué conforme à l'AI Act.
- **En continu** : crée les annonces, les lance sous plafond, met en pause ce
  qui ne convertit pas, réalloue vers ce qui convertit.
- **En continu** : trouve les prospects correspondant à l'ICP, les enrichit, les
  séquence dans la voix de la marque, et respecte l'opposition sans exception.
- **Chaque semaine** : dit ce qui a été fait, ce que ça a rapporté, et de combien
  il s'était trompé la semaine d'avant.
- **Chaque mois** : propose les corrections de la ligne éditoriale que les
  résultats justifient — et attend un oui.

Et une marque de plus ne coûte presque rien à ajouter, parce que tout est
multi-marques depuis la première table.

## Comment ça devient grand

| Palier | Mécanique | Ordre de grandeur |
| --- | --- | --- |
| **L'outil pour soi** | Egyptours, Oria. Zéro client, zéro revue d'app. | — |
| **Le cabinet** | 35 à 40 clients, 1 h 30 chacun par mois | 550 à 700 k€/an |
| **La marque blanche** | Les agences apportent les clients, on fournit l'outil | 100 agences à 300 €/mois = 30 k€/mois **sans livraison** ; 500 agences = 150 k€/mois |
| **Le libre-service** | La plateforme fait son propre démarrage | volume, panier faible |
| **Le jeu de données** | Vendre la réponse, plus l'outil | ce que personne d'autre ne peut vendre |

Les paliers ne se remplacent pas, ils s'empilent. Et chacun rend le suivant
moins cher, parce que le jeu de données grossit à chaque marque servie.

## Ce qui doit être vrai pour que ça marche

Honnêtement, et par ordre de fragilité — c'est la partie du document qu'il faut
relire tous les trimestres.

1. **Les portes de validation doivent rester tenables.** Si valider prend autant
   de temps que faire, le modèle s'écroule. C'est la seule hypothèse qui peut
   tuer le projet silencieusement.
2. **La qualité doit être jugeable par le client.** Un client qui ne peut pas
   juger finit par partir sans savoir pourquoi. D'où le rapport et l'écart
   affiché : ils servent autant à prouver qu'à mesurer.
3. **Les accès aux plateformes doivent rester ouverts.** Ils ont changé deux fois
   en 2026. Un connecteur par fichier, isolé.
4. **La boucle doit vraiment boucler.** Si les résultats ne corrigent jamais la
   ligne éditoriale, on n'est qu'un outil de plus — mieux fait, mais de plus.
5. **Il faut trouver les clients.** Toute la plateforme sert à en faire tenir
   quarante dans un agenda. Elle ne sert à rien s'il y en a trois.

Le point 5 est le plus probable, et c'est aussi celui qu'aucune ligne de code ne
résout.
