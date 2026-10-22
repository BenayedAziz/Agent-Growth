# Prompt Lovable — interface et charte graphique de l'outil (v2)

À coller tel quel dans un nouveau projet Lovable. Version du 2026-10-22, qui
remplace la première (bordeaux / orange / marron, angles droits — voir
l'historique Git). Demandes du fondateur : plus tech, plus ergonomique, les
informations importantes mises en avant, des chiffres plus grands, des angles
arrondis, les vrais visuels des posts (Instagram, X, TikTok), les publicités
qui marchent le mieux et ce qu'il faut améliorer, l'espace client, de vrais
beaux graphiques, et des couleurs originales, professionnelles et mémorables.

---

Je veux que tu conçoives l'interface complète d'un outil de pilotage marketing, avec sa propre charte graphique. Le rendu doit faire **produit tech haut de gamme** : professionnel, ergonomique, et assez singulier pour qu'on s'en souvienne après l'avoir vu une fois.

## 1. Le produit

Une plateforme où une petite agence — un consultant assisté par une IA — gère tout le marketing digital de plusieurs marques clientes : référencement Google et visibilité dans les IA (ChatGPT, Perplexity), contenus du site, réseaux sociaux (Instagram, TikTok, X, LinkedIn, Facebook), publicité (Meta, Google, TikTok, X), prospection et e-mailing.

Sa promesse tient en une phrase : **« voilà ce qu'un euro dépensé a rapporté, tous canaux confondus. »**

Deux types d'utilisateurs :
- **le consultant** : il pilote toutes les marques, repère ce qui marche et ce qui ne marche pas, prépare les contenus et les campagnes ;
- **le client** : un dirigeant de PME sans aucune formation marketing. Il veut savoir si ça marche, et valider ce qui sera publié en son nom.

## 2. Les principes qui commandent chaque écran

1. **Le résultat avant l'activité.** En haut de chaque écran : les clients gagnés, le chiffre d'affaires généré, ce que chaque client a coûté, ce que chaque euro a rapporté. Les likes, clics, vues et abonnés viennent en dessous, comme diagnostic — jamais en vedette.
2. **Les chiffres sont les héros.** Grands, très lisibles, avec leur évolution par rapport à la période précédente (flèche, pourcentage, couleur) et une mini-courbe de tendance. Format français : 12 480 €, 3,2 %, 1,4 k.
3. **Ce qui demande une décision passe devant.** Contenus à valider, publicité qui dépense sans rapporter, problème critique sur un site : visibles en premier, avec l'action à faire en un clic.
4. **Dire pourquoi, pas seulement combien.** À côté de chaque chiffre important, une phrase courte en français clair : « Ce post a marché parce que… », « Cette pub coûte 2 fois plus cher par client que les autres ».
5. **Une recommandation est une fourchette avec ses hypothèses**, jamais un chiffre seul : « +8 à +15 clients/mois si on double le budget de cette pub — hypothèse : coût par client stable ».
6. **L'honnêteté quand on ne sait pas.** Si un canal n'est pas encore mesuré, l'écran le dit (« pas encore connecté — voici comment le brancher ») au lieu de se remplir d'activité.
7. **Ergonomie d'outil pro** : barre latérale de navigation, sélecteur de marque et de période toujours accessibles en haut, palette de commandes (⌘K / Ctrl+K), raccourcis clavier pour valider (V) et refuser (R), filtres persistants, états de chargement en squelette, aucune page sans action évidente.

## 3. La charte graphique — à créer entièrement

**Couleurs : originales, professionnelles, mémorables.**
Interdit : le bleu SaaS standard, le violet, les dégradés bleu-violet, le gris ardoise par défaut de shadcn, le néon sur fond noir façon « cyberpunk ». Je veux une palette qu'on reconnaîtrait sur une capture d'écran sans voir le logo. **Propose 3 palettes**, donne à chacune un nom et une phrase sur ce qu'elle raconte, et applique celle que tu recommandes. La palette retenue comprend :
- une couleur de marque, une couleur d'action, des neutres (fonds, surfaces, bordures, textes) ;
- des couleurs d'état : succès, attention, danger, information — distinctes de la couleur de marque ;
- **une palette de données de 6 à 8 couleurs** pour les graphiques, distinguables entre elles, y compris par les daltoniens ;
- un mode clair et un mode sombre soignés tous les deux (le sombre doit faire très « outil tech », pas juste inversé) ;
- tous les couples texte/fond au contraste WCAG AA minimum.

**Typographie : originale.**
Interdites : Inter, Roboto, Open Sans, Lato, Poppins, Montserrat, Space Grotesk, DM Sans et les polices système. Propose 3 associations (titres, texte courant, et **une police pour les chiffres** — chiffres tabulaires, éventuellement une monospace pour le côté tech), explique ce que chacune raconte, applique celle que tu recommandes. Polices libres d'usage commercial (Google Fonts, Fontshare ou licence libre) : je les réutiliserai dans des rapports PDF.

**Formes : arrondies.** Une échelle de rayons cohérente (petits pour les badges et champs, moyens pour les boutons, plus généreux pour les cartes et panneaux). Ombres légères et rares, plutôt des surfaces et des bordures fines pour structurer.

**Ça ne doit pas avoir l'air généré par une IA.** Pas d'emojis, pas d'icônes « étincelles », pas de grand titre centré sur dégradé, pas d'illustrations 3D génériques, pas de rangées de cartes toutes identiques. De la hiérarchie : une information principale par zone, des tailles qui varient selon l'importance, une grille rigoureuse.

## 4. Les écrans à concevoir

Invente 4 marques clientes crédibles de secteurs différents (par exemple : une agence de voyage, une clinique esthétique, une banque, une boutique en ligne) et des données réalistes et cohérentes entre les écrans.

### 4.1 Le cockpit du consultant (accueil)
- En haut, 4 grands indicateurs tous clients confondus : clients gagnés ce mois, chiffre d'affaires généré, coût moyen par client, retour sur dépense publicitaire — chacun avec évolution et mini-courbe.
- **« À traiter maintenant »** : contenus en attente de validation, pubs qui dépensent sans résultat, alertes critiques — chaque ligne avec son bouton d'action.
- La liste des marques sous forme de tableau dense et lisible : résultat du mois, tendance, coût par client, budget consommé, santé (vert/orange/rouge), prochaine échéance.

### 4.2 La fiche d'une marque — vue d'ensemble
- Le résultat tous canaux : clients, chiffre d'affaires, dépense, retour par euro.
- Un grand graphique « dépense vs chiffre d'affaires » dans le temps.
- La contribution de chaque canal (SEO, réseaux, publicité, e-mailing) aux clients gagnés.
- « Ce qui marche » / « Ce qu'il faut améliorer » : 3 points chacun, en phrases claires, avec l'impact estimé en fourchette.

### 4.3 Réseaux sociaux — avec les vrais visuels
- Une grille des posts publiés, **affichés comme sur la plateforme** :
  - **Instagram** : image ou carrousel au format 4:5, réel au format vertical avec icône lecture ;
  - **TikTok** : vidéo verticale 9:16, miniature avec durée ;
  - **X** : le post tel qu'il apparaît (avatar, nom, texte, image éventuelle) ;
  - LinkedIn et Facebook dans le même esprit.
  Utilise de vraies photos d'illustration cohérentes avec chaque marque.
- Sur chaque post : portée, interactions, clics vers le site, et **clients ou demandes générés** quand c'est mesuré.
- **Le top 3 et le flop 3 du mois**, mis en avant, avec « pourquoi ça a marché / pourquoi pas ».
- Un calendrier de publication (semaine / mois) avec les posts programmés en miniature.
- Une carte de chaleur « meilleurs jours et heures pour publier ».

### 4.4 Publicité — ce qui rapporte, ce qu'on coupe
- En haut : dépense, clients gagnés, coût par client, retour par euro, pour Meta, Google, TikTok et X.
- **Le classement des publicités de la meilleure à la pire**, chacune avec son visuel ou sa vidéo (aperçu réel : pub Instagram/Facebook, annonce Google en texte, pub TikTok verticale), sa dépense, ses résultats, son coût par client.
- Un badge de verdict clair sur chaque pub : **« À augmenter », « À garder », « À corriger », « À couper »**, avec la raison en une phrase.
- **« Ce qu'il faudrait améliorer »** : recommandations concrètes (changer le visuel, l'audience, le message, le budget), chacune avec l'impact attendu en fourchette et un bouton pour préparer la modification (qui partira en validation).
- Une courbe de rythme de dépense vs budget du mois.

### 4.5 Référencement Google et visibilité IA
- Une note sur 100 en grande jauge, et trois piliers avec leur note : **Technique** (ce qui permet à Google de lire, comprendre et indexer le site), **On-Page** (ce qui signale à Google de quoi parle chaque page), **E-E-A-T** (ce qui établit la crédibilité du site).
- Les problèmes classés par gravité (critique, important, amélioration) avec « pourquoi » et « quoi faire ».
- Les mots-clés : sur lesquels le site apparaît (position, recherches par mois, évolution), et ceux où **les concurrents apparaissent et pas lui**.
- La vitesse du site sur mobile et ordinateur.
- La visibilité dans les IA : sur quelles questions ChatGPT ou Perplexity citent la marque, ou citent un concurrent à sa place.

### 4.6 La file de validation
- Chaque contenu est montré **exactement comme il sera publié** (aperçu Instagram, TikTok, X, page de site, e-mail, pub).
- Trois boutons : Valider, Demander une modification, Refuser — avec raccourcis clavier, et passage automatique au suivant.
- Pour les dépenses : le montant, le plafond, et ce qu'on en attend.
- Un historique : qui a validé quoi, quand.

### 4.7 L'espace client (vue simplifiée)
Le même produit, mais pour un dirigeant non spécialiste :
- **une seule question en haut : « Est-ce que ça marche ? »** — clients gagnés, chiffre d'affaires généré, ce que ça a coûté, en très grand, avec une phrase de synthèse ;
- ce qu'on a fait ce mois, en résumé visuel (les meilleurs posts en images, les pubs qui ont marché) ;
- ce qui attend sa validation, mis en évidence ;
- le rapport mensuel à télécharger ;
- aucun jargon : chaque terme technique est remplacé ou expliqué dans la phrase.

### 4.8 L'assistant
Un panneau latéral de discussion avec l'IA, accessible de partout, qui répond sur les données de la marque affichée (« Pourquoi les ventes ont baissé cette semaine ? ») et propose des actions qui partent en validation.

## 5. Les graphiques

Je veux de **vrais beaux graphiques**, pas des graphiques par défaut :
- courbes et aires pour les évolutions, barres pour comparer, entonnoir pour le parcours (vu → cliqué → demandé → client), carte de chaleur pour les horaires, mini-courbes dans les tableaux ;
- pas de camembert en 3D, pas plus de 6 séries par graphique ;
- infobulles précises au survol, légende directement sur les courbes quand c'est possible, comparaison avec la période précédente en pointillés ;
- axes discrets, grilles très légères, chiffres en format français ;
- chaque graphique a un titre qui dit la conclusion (« Le coût par client a baissé de 18 % depuis septembre »), pas seulement le sujet.

## 6. Ce que j'attends en sortie

1. **Une page « Charte »** : les 3 palettes proposées et celle retenue, la typographie (3 associations, celle retenue, échelle de tailles, usage des chiffres), les rayons, espacements, ombres, la grille, tous les composants (boutons, champs, cartes d'indicateurs, tableaux, badges de verdict et de gravité, jauges, aperçus de posts par plateforme, carte de validation, alertes, navigation, palette de commandes), les graphiques types, les modes clair et sombre, et le ton des textes (tutoiement, phrases courtes, zéro jargon, exemples avant/après).
2. **Les design tokens** en variables CSS et configuration Tailwind, prêts à être réutilisés hors de Lovable.
3. **Tous les écrans de la section 4**, navigables entre eux, avec les données fictives cohérentes.

Commence par la page Charte, fais-moi valider la palette et la typographie, puis enchaîne les écrans dans l'ordre : cockpit, fiche marque, réseaux sociaux, publicité, référencement, validation, espace client, assistant. Desktop d'abord (le mobile viendra plus tard). Tout en français.
