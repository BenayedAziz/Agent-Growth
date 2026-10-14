# Décisions

Les choix structurants, avec leur raison et leur date. Utile dans six mois,
quand on aura oublié pourquoi.

---

## ADR-001 — La ligne éditoriale est un fichier, pas un prompt

*2026-10-11 · adopté*

**Problème.** Un agent qui écrit un post lundi et une annonce mardi produit deux
marques différentes, parce que le positionnement est rédigé à neuf dans chaque
prompt.

**Décision.** Le positionnement, le ton, les piliers et les interdits vivent
dans `brand-core.json`. Tous les outils le lisent. Aucun ne le redécide.

**Conséquences.** La cohérence devient vérifiable au lieu d'être espérée. En
contrepartie, `schemas.py` devient un contrat : le modifier affecte tous les
outils, d'où le `SCHEMA_VERSION`.

---

## ADR-002 — Python, pas de framework d'agents

*2026-10-11 · adopté*

**Décision.** Python pur avec le SDK Anthropic. Pas de LangGraph, CrewAI ni
équivalent.

**Pourquoi.** Les outils sont séquentiels : lire des pages, analyser, écrire des
fichiers. Une fonction suffit. Un framework ajouterait une abstraction à
apprendre, à déboguer et à maintenir, sans rien résoudre. Python parce que le
crawl, le SEO et le scraping y sont les mieux outillés, et parce que les skills
de contenu disponibles sur GitHub y sont déjà écrites.

**À réexaminer si** on a besoin de véritable parallélisme sur des dizaines de
marques, ou de reprise sur incident en milieu de traitement.

---

## ADR-003 — Des fichiers, pas de base de données

*2026-10-11 · adopté*

**Décision.** Un dossier par marque dans `brands/<slug>/`.

**Pourquoi.** On peut relire, corriger à la main, versionner, envoyer au client.
Une base de données imposerait un schéma, des migrations et un serveur pour un
bénéfice nul à cette échelle.

**À réexaminer si** plusieurs personnes doivent travailler simultanément sur la
même marque, ou si l'historique des versions devient un besoin produit.

---

## ADR-004 — Réutiliser les skills de rédaction existantes

*2026-10-11 · adopté*

**Question posée.** Peut-on intégrer une skill Instagram publique
(`Jakeschincariol/instagram-agent-skill`) plutôt que développer l'agent ?

**Ce que ce dépôt contient réellement**, d'après son README (MIT, ~950 étoiles,
2 commits au moment de l'examen) :

- 13 skills Claude pour Instagram : scripts de Reels et notation d'accroches,
  légendes, recherche de contenus performants, audit de profil, planning
  hebdomadaire, nettoyage de textes ;
- des scripts Python locaux, sans dépendance et sans accès réseau ;
- **aucune authentification, aucune clé API, aucune publication.** Son README
  l'écrit explicitement : « rien n'est publié tant que vous ne dites pas oui »,
  et automatiser la publication, les commentaires, les abonnements ou les
  messages privés viole les conditions d'utilisation d'Instagram ;
- une honnêteté notable sur ses limites : l'auteur indique que son score
  d'accroche repère bien les accroches faibles (AUC 0,83) mais ne distingue pas
  les gagnantes parmi les bonnes (AUC 0,56, où 0,50 est le hasard).

**Décision.** Oui, le réutiliser — pour la **couche création**, copié et épinglé
dans `skills/vendor/`, après lecture de chaque fichier. Non, cela ne remplace
pas l'agent.

**Pourquoi.** Ce dépôt fait gagner du savoir-faire rédactionnel Instagram, ce
qui est réel et appréciable. Il ne fait rien de ce qui constitue le produit :
stratégie de marque, SEO et corrections sur le site, chiffrage des
opportunités, lancement et pilotage des campagnes, cohérence entre canaux,
mesure. Et il ne publie pas : « la gestion automatisée d'un compte Instagram »
reste à faire, et passe par la Content Publishing API de Meta — app
développeur, compte professionnel, Page liée, revue d'application.

**Précautions.** Une skill est composée d'instructions que Claude suit et de
scripts qu'il exécute. On ne dépend pas d'un dépôt tierce-partie par
sous-module : on copie, on épingle le commit, on relit. Procédure dans
[ARCHITECTURE.md](ARCHITECTURE.md#brancher-une-skill-externe). Les scores
produits par une skill externe sont présentés comme des indications, jamais
comme des vérités.

---

## ADR-005 — Aucun chiffre sans ses hypothèses

*2026-10-11 · adopté*

**Décision.** Toute estimation est un objet `Estimate` : une fourchette, la
liste des hypothèses, et l'origine du chiffre (`donnees_site`,
`benchmark_secteur`, `hypothese`). Le schéma l'impose ; ce n'est pas une
consigne de rédaction.

**Pourquoi.** La valeur promise est « des conseils avec des estimations
chiffrées » pour des gens qui ne peuvent pas vérifier ces chiffres eux-mêmes.
Un chiffre faussement précis est donc plus dangereux qu'une fourchette large.
Rendre les hypothèses obligatoires rend aussi l'estimation corrigible : quand
le réel diffère, on sait quelle hypothèse était fausse.

---

## ADR-006 — Pas d'automatisation non officielle des réseaux

*2026-10-11 · adopté*

**Décision.** Publication, commentaires, abonnements et messages privés passent
exclusivement par les API officielles. Pas de navigateur piloté, pas de client
non officiel, même si c'est plus rapide à construire.

**Pourquoi.** C'est une violation des conditions d'utilisation d'Instagram et
de LinkedIn, et le risque porte sur le compte du client. Un compte client fermé
n'est pas un incident technique, c'est une faute professionnelle.

**Conséquence.** Tant qu'un accès officiel n'est pas en place, les outils
préparent le contenu et le remettent à valider. C'est déjà l'essentiel du
travail, et c'est vendable tel quel.

---

## ADR-007 — Le pré-test comme réflexe, pas comme promesse

*2026-10-11 · adopté*

**Décision.** Tout outil qui produit une création produit des variantes et les
confronte avant diffusion.

**Pourquoi.** L'intérêt concret est de réduire le coût du raté créatif :
écarter trois accroches faibles coûte beaucoup moins cher qu'une campagne qui ne
parle à personne.

**Limite assumée.** Un pré-test écarte les ratés évidents ; il ne prédit pas les
succès. Les outils affichent cette limite au lieu de la masquer derrière un
score — c'est précisément ce que le dépôt Instagram examiné en ADR-004 mesure
sur ses propres accroches, et il a raison de le dire.

---

## ADR-008 — Se placer dans le trou de marché : français, TPE/PME, humain inclus

*2026-10-13 · adopté · **tarification amendée par ADR-010***

**Problème.** Le marché est-il déjà pris ? Deux concurrents directs ont été
examinés.

**Okara** (Singapour, 2025, 2-10 personnes, financement non divulgué). Lit le
site, produit un document de stratégie, fait tourner des agents SEO, GEO,
contenu, réseaux (Reddit, X, LinkedIn, Hacker News) et influence. Gratuit
(20 crédits) puis 66 $/mois (2 000 crédits). Critiqué par une publication tech
comme « buggy Claude wrapper », sorties de faible qualité, auto-posting Reddit
et Hacker News à risque de ban. Source unique, aucun benchmark indépendant.

**Collision** (`usecollision.com`, anglophone). « The AI you hire to run
growth — replace your entire growth team. » Une conversation, **une mémoire,
une source de vérité**, validation humaine sur chaque action, ~16 surfaces.
Tarifs annoncés sur ses propres pages comparatives : 500-1 000 $/mois (Launch),
2 000-6 000 $/mois (Growth), 8 000-15 000 $/mois (Scale). Pas de page de prix
publique, contact = démo : vente assistée. Il écrit lui-même que son palier
« se situe délibérément entre les outils de commodité et un growth hire humain
à 5-25 k$/mois ».

**La structure du marché qui en découle :**

| Palier | Qui | Ce qu'on y trouve |
| --- | --- | --- |
| 0-70 €/mois | Okara et beaucoup d'autres | Une couche de rédaction. Qualité contestée. |
| **100-400 €/mois** | **personne** | **le trou** |
| 500-15 000 $/mois | Collision | Vente assistée, anglophone, startups et growth teams |
| 5-25 k$/mois | growth hire humain | — |

**Décision.** Se placer dans le trou : **abonnement à prix bas, en français,
pour des TPE/PME, avec un humain responsable derrière.** Pas de ticket d'entrée
à 5 000 € — il exclut la cible. Un frais d'installation modeste ou un engagement
de quelques mois, pas davantage.

**Pourquoi ce trou tient.** Collision ne descendra pas : il le dit lui-même, et
sa vente assistée ne supporte pas un panier à 250 €. Okara ne montera pas : 2 à
10 personnes, aucune capacité de service, et son modèle à 66 $/mois interdit
toute heure humaine. Ni l'un ni l'autre n'est francophone, ni ne connaît la
fiche Google Business d'un artisan, ni ne touchera au WordPress du client.

**Ce qui n'est pas un différenciateur, contrairement à ce qu'on croyait.** La
validation humaine obligatoire : Collision la met en avant exactement comme
nous. Elle reste une bonne règle (ADR-006), elle ne reste pas un argument.

---

## ADR-009 — Ne pas écrire ce qui existe déjà sous licence MIT

*2026-10-13 · adopté*

**Constat.** La couche « savoir marketing » est abondante, gratuite et mieux
maintenue que ce qu'on produirait.

- **`coreyhaines31/marketingskills`** — ~40 skills MIT, 54,5 k étoiles,
  8,1 k forks, 1 027 commits. Couvre `seo-audit`, `ai-seo`, `schema`,
  `site-architecture`, `programmatic-seo`, `competitors`, `ads`, `ad-creative`,
  `social`, `copywriting`, `cro`, `cold-email`, `emails`, `analytics`,
  `ab-testing`, `content-strategy`, `launch`, `pricing`… Auteur crédible
  (Conversion Factory, ex-Baremetrics).
- **`VoltAgent/awesome-agent-skills`** — annuaire de 1 497+ skills, MIT,
  35,6 k étoiles.

**Le point qui fait mal.** Sa skill `product-marketing` crée
`.agents/product-marketing.md` — produit, audience, personas, douleurs, paysage
concurrentiel, différenciation, objections et anti-personas, dynamiques de
bascule, langage client (mots à employer et à éviter), voix de marque, preuves,
objectifs — et **« toutes les autres skills la consultent en premier »**.
C'est notre ADR-001, avec 54,5 k étoiles et deux ans d'avance.

**Donc : notre architecture n'est pas différenciante.** Il faut le dire au lieu
de le contourner.

**Ce qui reste réellement à nous :**

| | `product-marketing` | notre `brand-core` |
| --- | --- | --- |
| Rempli par | un entretien, ou le dépôt de code | **un crawl du site et des concurrents** |
| Forme | prose Markdown | **schéma typé et validé** |
| Chiffrage | aucun | **fourchettes + hypothèses + origine, imposées par le schéma** |
| Opportunités | aucune | **6 à 10, classées par rentabilité** |
| Cible | marketeurs techniques, SaaS | **TPE/PME francophones, zéro connaissance** |
| Langue | anglais | français |

Le premier point est le plus important : un dirigeant de TPE ne remplira jamais
un questionnaire en douze sections. Qu'on le génère depuis son site en deux
minutes n'est pas un détail d'ergonomie, c'est ce qui rend l'onboarding possible.

**Décision.**

1. **Ne pas écrire** `seo-audit`, `ads`, `social`, `copywriting`, `cro`,
   `cold-email`, `schema`, `programmatic-seo`, `competitors`, `ai-seo`,
   `analytics`. Les vendoriser (`scripts/vendor-skill.sh`).
2. **Écrire un pont** `brand-core` → `.agents/product-marketing.md`, pour que
   ces skills héritent de la marque sans saisie. Un pont de quelques heures
   débloque ~40 skills.
3. **Reprendre d'elles ce qui est meilleur** : le versionnage avec journal des
   changements, les anti-personas, les dynamiques de bascule (poussée,
   attraction, habitude, anxiété), le langage client verbatim.
4. **Concentrer l'ingénierie** sur les trois choses qu'aucune librairie de
   skills ne fait : appliquer les corrections sur le vrai site, le reporting de
   livraison, et la couche locale française (fiche Google Business, SEO local).

**Précaution.** Vendoriser reste copier-et-épingler après relecture
(ADR-004). Ces dépôts cumulent 1 000+ commits et des contributions externes
ouvertes : une mise à jour non relue change le comportement du produit.

---

## ADR-010 — Mener avec le GEO, tarifer 500-5 000 €, et ne pas reconstruire GoHighLevel

*2026-10-13 · adopté · amende ADR-008 sur la tarification*

Appuyé sur [l'étude de marché](ETUDE-MARCHE.md), qui porte les sources.

**1. L'offre mène avec le GEO/AEO, plus avec le SEO.**

Le CTR organique chute de 58 à 61 % quand une réponse IA s'affiche, et l'effet
accélère : Ahrefs mesure −34,5 % puis −58 % en un an sur la même métrique, et
près d'une requête sur deux est désormais concernée. Pendant ce temps, le
retainer médian GEO/AEO est à 6 850 $/mois, en hausse de 66 % depuis début 2024.

Promettre « du trafic Google » vend un actif en fonte, et le client le
constatera vers le sixième mois — précisément quand le risque de départ est
maximal. Le SEO technique reste traité, mais comme un acquis, pas comme
l'argument.

**2. Tarification : 500 à 5 000 €/mois, indexée sur les pages, l'accompagnement
et les offres activées.** Amende le « 100-400 €/mois » d'ADR-008.

La raison n'est pas commerciale, elle est arithmétique. Acquérir un client PME
coûte entre 141 $ (recommandation) et 1 980 $ (prospection sortante), médiane
services B2B ~1 840 $. À 250 €/mois sur 24 mois, le ratio valeur-vie / coût
d'acquisition tombe à 3,3:1 — et à 1,6:1 si le client ne reste qu'un an. À
1 500 €/mois, il est à 19,6:1, ce qui finance un appel de vente, une démo, et
de la publicité. **Un prix bas interdit d'acquérir ; c'est le prix qui rend le
scale possible, pas l'inverse.**

Le ticket d'entrée à 5 000 € reste écarté : la référence de marché pour une
mise en place est de 200 à 500 $. On retient 490-990 € une fois.

**3. On ne reconstruit pas la plateforme centralisée.**

GoHighLevel vend déjà exactement ça : 297 $/mois en marque blanche, 497 $/mois
avec caisse Stripe, création automatique des sous-comptes et refacturation à sa
propre marge, ~75 % de marge brute pour l'agence. Vendasta propose 250+ produits
martech en marque blanche. Leur fossé n'est pas l'IA, c'est l'étendue des
intégrations — des années-hommes.

En revanche aucun des deux ne fait ce qu'on fait : brand-core depuis un crawl,
GEO/AEO, correctifs appliqués sur le vrai site, marquage de contenu conforme à
l'AI Act. **On construit la couche qui leur manque, quitte à tourner au-dessus
d'eux.** Et le scale réel, à terme, c'est de leur vendre cette couche — 100
agences à 300 €/mois sans aucune livraison client — mais pas avant de l'avoir
prouvée sur de vrais clients.

**4. La spécialisation métier devient la décision structurante.**

Elle améliore simultanément les trois variables du modèle : la marge (le
deuxième client d'un même métier coûte la moitié du temps du premier), la
rétention (corrélation établie sur ~200 k comptes PME) et l'acquisition (la
recommandation est le canal le moins cher, à 141-200 $, et elle circule à
l'intérieur d'un métier). Aucune ligne de code ne produit un effet comparable.

**5. Le palier bas est une porte d'entrée, pas un produit.**

Wix embarque déjà un assistant SEO et la génération automatique de balises ;
Shopify a Sidekick et Magic. C'est le palier à 490 € qu'ils rendront gratuit en
premier. À surveiller trimestriellement : si l'un d'eux publie un module
GEO/AEO correct inclus, toute la grille doit remonter.

---

## ADR-011 — Le marquage des contenus générés est une fonctionnalité, pas une mention légale

*2026-10-13 · adopté*

**Contrainte.** L'article 50 de l'AI Act européen est **en vigueur depuis le
2 août 2026**. Tout système qui génère du texte, de l'image, de l'audio ou de
la vidéo doit signaler ces contenus, quel que soit son niveau de risque, et les
marquer de façon lisible par machine — les systèmes antérieurs au 2 août
bénéficient d'un délai jusqu'au 2 décembre 2026. Les obligations haut risque
sont reportées à décembre 2027 et août 2028.

**Décision.** Tout outil qui publie du contenu pour une marque européenne
produit le signalement et le marquage. Ça se construit dans le pipeline de
publication (`site-publish`, `social-publish`), pas dans les conditions
générales.

**Et c'est un argument commercial.** Okara est singapourienne, Collision
américaine. Savoir expliquer sa conformité à un dirigeant français ou allemand
est un avantage qui ne s'improvise pas.

**Réserve.** Les sources sont des cabinets juridiques et des blogs
spécialisés, pas le Journal officiel. À faire valider par un juriste avant tout
engagement contractuel envers un client.

---

## ADR-012 — Le produit est la console multi-marques, pas un canal

*2026-10-13 · adopté · amende ADR-003 sur le stockage*

**Erreur de cadrage corrigée.** Les décisions précédentes ont progressivement
fait du SEO/GEO le centre du produit, parce que c'est là que l'étude de marché
avait le plus de données chiffrées. C'est une erreur : le SEO et le GEO sont
deux canaux parmi huit.

**Décision.** Le produit est **une console qui pilote le marketing digital de
plusieurs marques à la fois** : ligne éditoriale par marque, contenu organique
quotidien programmé, publicité générée et pilotée, résultats de tous les canaux
au même endroit, reporting automatique, accès client en lecture. Les canaux sont
des modules. Spécification et plan de construction :
[PLATEFORME.md](PLATEFORME.md).

**Ce qui ne change pas.** La ligne éditoriale reste la colonne vertébrale
(ADR-001) : c'est elle qui rend cohérent ce qu'on publie sur huit canaux.
`brand-core` reste le premier module, et il est construit.

**Ce qui change : il faut une base de données.** Des fichiers suffisaient pour
une analyse de marque. Ils ne suffisent pas pour des séries temporelles
multi-marques, des jetons OAuth à rafraîchir et des tâches planifiées chaque
nuit. ADR-003 est amendé sur ce point : les fichiers restent le format des
livrables lisibles (`brand-core.md`, les rapports), la base porte l'état
opérationnel.

Une seule table porte toute l'intelligence de reporting :
`Mesure(marque, canal, métrique, date, valeur)`. Tous les écrans et tous les
rapports se calculent dessus — c'est ce qui évite un écran spécifique par
plateforme.

---

## ADR-013 — Construire d'abord pour ses propres marques, parce que les portes sont ouvertes

*2026-10-13 · adopté*

**Constat qui décide de l'ordre.** Les plateformes laissent lire facilement,
mais filtrent l'écriture **pour le compte d'autrui**.

Pour ses propres comptes : OAuth suffit sur Analytics et Search Console ; les
*developer tokens* Google Ads ont été supprimés le 9 septembre 2026 et l'accès
« Basic » est désormais accordé automatiquement en quelques minutes après
vérification de marque du projet Cloud ; un jeton d'utilisateur système suffit
sur ses propres comptes Meta Ads, sans revue d'app ; la publication Instagram
fonctionne en mode développement. Seule la fiche Google Business impose une
revue manuelle, d'environ 14 jours.

Pour les comptes de clients : Advanced Access, revue d'app par permission avec
vidéo de démonstration, vérification d'entreprise avec documents légaux — de
deux à six semaines par soumission.

**Décision.** La phase 1 sert les marques du fondateur (Egyptours, Oria) et ne
demande **aucune revue d'app**. Les dossiers de revue se déposent **en parallèle**
de la phase 3, pas après, parce que le délai est du temps de calendrier qu'on ne
compresse pas.

**Corollaire d'architecture.** Un connecteur par fichier, derrière une interface
commune. Les règles d'accès ont changé deux fois en 2026 : une rupture ne doit
casser qu'un connecteur.

**Réserve.** Ces règles bougent et les sources sont majoritairement des guides
tiers. À revérifier dans la documentation officielle au moment de brancher
chaque plateforme.

---

## ADR-014 — La mesure est le produit ; on produit beaucoup pour publier peu

*2026-10-14 · adopté · amende ADR-010 (« mener avec le GEO ») et le module 4*

Issu du raisonnement en premiers principes, consigné dans
[PREMIERS-PRINCIPES.md](PREMIERS-PRINCIPES.md), qui devient la méthode de
décision du projet.

**Le test qui tranche.** Pour chaque fonctionnalité : *le client peut-il
l'obtenir gratuitement ailleurs ?*

| Fonction | Gratuite ailleurs ? |
| --- | --- |
| Écrire un post, une annonce, un article | **Oui** — ChatGPT gratuit |
| Générer un visuel | **Oui** |
| Suivre ses chiffres canal par canal | **Oui** — chaque plateforme a son tableau de bord |
| Savoir **quoi** dire, pour **sa** marque | Non |
| Savoir si un euro dépensé en a rapporté plus d'un, **tous canaux confondus** | **Non. Personne ne le lui donne.** |

**Décision 1 : la mesure n'est pas le module 6, c'est le produit.** Un système
qui prouve le retour sans produire de contenu se vend ; un système qui produit
du contenu sans prouver le retour ne se vend pas longtemps. Les modules contenu
et publicité sont des commodités nécessaires, pas l'argument.

Ça amende ADR-010 : le GEO est mieux payé que le SEO, mais les deux restent des
moyens. L'argument de vente devient « voilà ce qu'un euro a rapporté, tous
canaux confondus ».

**Décision 2 : le résultat s'affiche avant l'activité.** La rareté est passée de
la production au jugement : produire est gratuit, donc produire ne vaut rien.
Un écran qui ouvre sur des abonnés, des clics et des visites répond à la
mauvaise question — ces chiffres sont là parce que les plateformes les donnent
facilement, pas parce qu'ils disent si ça marche.

Mis en œuvre dans le code, pas seulement dans la doc : `store.py` sépare
`ACQUISITION_METRICS`, `REVENUE_METRICS` et `COST_METRICS` du reste, `outcome()`
renvoie acquisitions, coût et coût par acquisition avec la période précédente,
`activity()` renvoie le diagnostic, et la console ouvre sur le premier. Quand
rien n'est mesuré, elle le dit au lieu de remplir la place — `cpa` vaut `None`
et non zéro, parce que « on ne sait pas » et « c'est gratuit » ne doivent jamais
s'afficher pareil.

**Décision 3 : le module contenu produit beaucoup pour publier peu.** Si
produire est gratuit, tout le monde publiera chaque jour, et l'attention reste
fixe : le contenu quotidien sera le bruit de fond, pas un avantage. Trente
publications produites et les quatre meilleures publiées battent trente
publiées. **Le taux de rejet devient un indicateur de qualité, pas un
gâchis** — et il s'affiche comme tel.

Ça amende la description du module 4 dans [PLATEFORME.md](PLATEFORME.md) : la
capacité de production sert à jeter.

**Décision 4 : la marque blanche est la seule voie de croissance saine.** Ce qui
plafonne un cabinet n'est pas la livraison — l'automatisation la réduit — c'est
le **transfert de confiance**, qui se construit à vitesse humaine, une relation
à la fois. La marque blanche emprunte une confiance déjà construite : l'agence a
celle de son client, on fournit la machine. Le libre-service ne marche que là où
la confiance n'est pas requise, c'est-à-dire sur les petits paniers.

**Pourquoi les gros ne suivront pas.** Pas parce qu'ils sont lents : parce que
leur modèle de revenus le leur interdit. HubSpot vend des sièges et des crédits
d'usage — un agent autonome, c'est moins de sièges. GoHighLevel vend un
constructeur — un système qui n'a pas besoin d'être construit retire la raison
de payer. Les agences vendent du temps. C'est une contrainte de trésorerie, pas
d'ingénierie, et c'est la seule sorte de fossé qui tient face à quelqu'un de
cent fois plus gros.
