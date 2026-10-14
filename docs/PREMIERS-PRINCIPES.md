# Premiers principes

*Ce document est la méthode de raisonnement du projet. Il ne décrit pas ce qu'on
construit — il décrit comment on décide quoi construire, et ce que ce
raisonnement a déjà fait changer d'avis.*

## La méthode

Raisonner en premiers principes, c'est retirer tout ce qui n'est là que parce
que « c'est comme ça que ça se fait », descendre jusqu'à ce qui est
irréductible, et reconstruire depuis là. Le test est simple : **si une décision
s'explique par « les autres font comme ça », elle n'est pas fondée.**

Appliqué ici, ça donne quatre questions qu'on se repose à chaque arbitrage :

1. Qu'achète réellement le client ? (pas ce qu'on lui vend)
2. Qu'est-ce qui a physiquement changé, et qu'est-ce qui n'a pas changé ?
3. Quelle est la ressource rare ?
4. Qu'est-ce qui empêche structurellement un concurrent de faire pareil ?

## 1. Ce qu'un client achète

Une entreprise n'achète ni des publications, ni des positions sur Google, ni des
abonnés. Elle achète **des clients de plus, à un coût inférieur à ce qu'ils
rapportent.**

Le reste — SEO, publicité, contenu, réseaux — ce sont des *moyens*, qui ont été
les meilleurs disponibles à un moment de l'histoire. Les confondre avec la
finalité est l'erreur la plus courante du métier, et c'est celle qu'on a
commise en mettant le SEO au centre pendant deux jours.

La boucle irréductible n'a que cinq étapes :

```
un besoin → une recherche (ou une portée) → une rencontre avec la marque
          → une conviction → un achat
```

Le marketing, c'est augmenter le débit de cette boucle par euro dépensé. Rien
d'autre.

## 2. Ce qui a changé, et ce qui n'a pas changé

C'est la question qui dit s'il y a une place à prendre.

**Ce qui s'est effondré** — le coût de produire une unité de persuasion :

| | Avant | Maintenant | Facteur |
| --- | --- | --- | --- |
| Une vidéo publicitaire de 10 s | ~2 000 € et 2 semaines | ~0,50 € et 40 secondes | ×4 000 |
| Un article de fond | ~300 € | ~0,05 € | ×6 000 |
| Une analyse concurrentielle | 2 jours de consultant | quelques minutes | ×100 |

**Ce qui n'a pas changé d'un pouce :**

- **L'attention.** Il y a toujours 24 heures dans une journée, et personne ne
  lira plus qu'avant.
- **La confiance.** Elle s'accumule à vitesse humaine. Aucun modèle ne
  l'accélère.
- **L'accès à la distribution.** Les plateformes le contrôlent, et elles le
  resserrent.
- **Le fait de savoir quoi dire.** Ça demande de connaître la marque et son
  client.

## 3. La ressource rare a changé de place

Quand la production tombe à zéro et que l'attention reste fixe, **la rareté
passe de la production au jugement.** Tout le monde peut désormais produire à
l'infini ; donc produire ne vaut plus rien.

Ce qui vaut quelque chose : **décider quoi produire, et prouver que ça a
marché.**

Deux conséquences, et la seconde est désagréable.

### Ça valide la ligne éditoriale et la boucle de mesure

La ligne éditoriale, c'est du jugement encodé. La boucle de mesure, c'est la
preuve. Ce sont les deux seules choses rares. Elles étaient déjà au centre du
projet — par chance plus que par raisonnement, et maintenant par raisonnement.

### Ça invalide « du contenu organique chaque jour »

Si produire est gratuit, **tout le monde publiera chaque jour.** Le contenu
quotidien ne sera donc pas un avantage : ce sera le bruit de fond. Et comme
l'attention est fixe, publier plus dans un espace saturé fait baisser la
performance moyenne de chaque publication.

L'avantage n'est pas le volume, c'est **la sélection**.

> Produire trente publications par mois et n'en publier que les quatre qui
> gagnent au pré-test est strictement supérieur à en publier trente.

La capacité de production sert donc à **jeter**, pas à publier. C'est exactement
l'idée de départ du projet — réduire le coût du raté créatif en pré-testant à
grande échelle — mais appliquée à l'organique, pas seulement à la publicité.
Le module de contenu doit donc avoir un taux de rejet élevé et assumé, et ce
taux est un indicateur de qualité, pas un gâchis.

## 4. Ce que le client ne peut pas obtenir gratuitement

Test décisif pour chaque fonctionnalité : **le client peut-il l'avoir sans
nous, gratuitement ?**

| Fonction | Peut-il l'avoir gratuitement ? |
| --- | --- |
| Écrire un post, une annonce, un article | **Oui.** ChatGPT gratuit le fait. |
| Générer un visuel | **Oui.** |
| Suivre ses chiffres canal par canal | **Oui.** Chaque plateforme a son tableau de bord. |
| Savoir **quoi** dire, pour **sa** marque, et pourquoi | Non. |
| Savoir si un euro dépensé a rapporté plus d'un euro, **tous canaux confondus** | **Non. Personne ne lui donne ça.** |
| Que ce soit fait, chaque jour, sans lui | Non. |

Les trois dernières lignes sont le produit. Les trois premières sont des
commodités qu'il faut avoir mais qui ne se vendent pas.

**Conséquence sur l'ordre de construction :** la mesure et la preuve ne sont pas
le module 6, ce sont *le* produit. Le contenu et la publicité sont des
accessoires que n'importe qui peut brancher. Un système qui prouve le retour sur
euro sans produire de contenu se vend ; un système qui produit du contenu sans
prouver le retour ne se vend pas longtemps.

C'est pour ça que `measure(marque, canal, métrique, jour, valeur)` est la table
centrale du schéma, et c'est pour ça que l'écart entre l'estimation annoncée et
le réel est affiché au lieu d'être caché.

## 5. Ce que le tableau de bord doit montrer en premier

Si le client achète des clients de plus à un coût connu, alors le premier écran
doit répondre à **une seule question** : combien de clients, à quel coût.

Un tableau de bord qui ouvre sur des abonnés, des clics et des visites montre de
**l'activité**, pas du **résultat**. C'est de la pensée héritée : ces chiffres
sont là parce que les plateformes les donnent facilement, pas parce qu'ils
répondent à la question.

Donc, dans la console :

- **En haut, le résultat** : clients ou prospects acquis, coût total, coût par
  acquisition. Par marque, et pour l'ensemble du portefeuille.
- **En dessous, le diagnostic** : clics, visites, abonnés — utiles pour
  comprendre *pourquoi*, jamais pour dire *si ça marche*.
- **Et quand il n'y a pas de résultat mesuré, le dire franchement**, au lieu de
  remplir l'écran avec de l'activité.

## 6. Pourquoi un concurrent beaucoup plus gros ne peut pas suivre

La réponse habituelle — « ils sont lents » — est fausse. Ils ont plus
d'ingénieurs que nous n'en aurons jamais.

La vraie réponse est que **leur modèle de revenus leur interdit le
comportement.**

| Acteur | Ce qu'il vend | Pourquoi l'autonomie le menace |
| --- | --- | --- |
| HubSpot | des sièges et des crédits d'usage | Un agent qui fait le travail sans humain, c'est moins de sièges vendus. |
| GoHighLevel | un constructeur de tunnels | Un système qui n'a pas besoin d'être construit retire la raison de payer. |
| Les agences | du temps de spécialiste | Facturer le résultat au lieu du temps divise leur chiffre d'affaires. |
| Semrush et consorts | de l'outillage à l'acte | Un système qui décide seul rend l'outil invisible. |

Aucun d'eux ne peut aller là sans réduire son propre revenu. C'est une
contrainte de trésorerie, pas d'ingénierie — et c'est la seule sorte de fossé
qui tient face à quelqu'un de cent fois plus gros.

## 7. Ce qui plafonne vraiment un cabinet

On a d'abord dit : la livraison, parce qu'elle consomme des heures. C'est vrai,
mais ce n'est pas irréductible — l'automatisation la réduit.

Ce qui est irréductible, c'est **le transfert de confiance.** Un client signe
parce qu'il fait confiance à quelqu'un. La confiance ne se duplique pas avec du
logiciel : elle se construit à vitesse humaine, une relation à la fois.

Donc la marque blanche n'est pas « le meilleur levier » par préférence : c'est
**la seule voie de croissance structurellement saine**, parce qu'elle emprunte
une confiance déjà construite. L'agence a déjà celle de son client ; on fournit
la machine.

Et le libre-service ne marche que là où la confiance n'est pas requise — c'est-
à-dire sur les petits paniers, là où le client accepte de risquer peu.

## 8. Ce que ce raisonnement a déjà fait changer

| Décision initiale | Ce que les premiers principes imposent |
| --- | --- |
| Mettre le SEO au centre | Le SEO est un moyen daté. Le centre est la boucle besoin → achat. |
| Mener avec le GEO | Mieux, mais toujours un canal. On mène avec **la preuve du retour**. |
| Contenu organique quotidien | Produire beaucoup pour **publier peu**. Le taux de rejet est un indicateur de qualité. |
| Tableau de bord par canal | Résultat en haut, activité en dessous. |
| La mesure en module 6 | La mesure **est** le produit. |
| La marque blanche comme levier | La marque blanche comme **seule** voie saine, parce que la confiance ne scale pas. |

## Les questions à reposer à chaque arbitrage

1. Le client peut-il l'avoir gratuitement ailleurs ? Si oui, c'est une commodité.
2. Est-ce que ça augmente le débit de la boucle besoin → achat, ou juste
   l'activité ?
3. Qu'est-ce qui est rare ici : la production, ou le jugement ?
4. Pourquoi un concurrent dix fois plus gros ne le fait-il pas ? Si la réponse
   n'est pas « son modèle de revenus le lui interdit », le fossé est fragile.
5. Est-ce qu'on le fait parce que c'est fondé, ou parce que tout le monde le
   fait ?
