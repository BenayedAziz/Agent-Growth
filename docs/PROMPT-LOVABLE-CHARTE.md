# Prompt Lovable — charte graphique de l'outil

À coller tel quel dans Lovable (nouveau projet). Rédigé le 2026-10-22 à partir
des indications du fondateur : bordeaux, orange énergique, marron terne, un peu
d'italique, aucune rondeur, une police originale, rien qui fasse « généré par IA ». Les valeurs exactes des couleurs sont laissées à
Lovable.

---

Je construis un outil de pilotage marketing, et je veux que tu crées sa **charte graphique complète**, puis que tu l'appliques sur quelques écrans clés pour la montrer en situation.

**Le projet**
C'est une plateforme où une petite agence (un consultant, assisté par une IA) gère tout le marketing digital de plusieurs marques clientes : audit SEO et visibilité dans les IA (ChatGPT, Perplexity), contenus du site, réseaux sociaux, publicité Google/Meta/TikTok, prospection, et surtout **la mesure : ce qu'un euro dépensé a rapporté**.
Il y a deux espaces :
- **l'espace consultant** : il voit toutes ses marques, lance les audits, prépare les contenus et les campagnes ;
- **l'espace client** : un dirigeant de PME, sans aucune formation marketing, y voit ses résultats et valide (ou refuse) ce qui va être publié sur son site et ses réseaux.

**Ce que la charte doit servir**
- **Le résultat avant l'activité** : en haut de chaque écran, les clients gagnés et ce qu'ils ont coûté ; les clics, visites et abonnés viennent en dessous, comme diagnostic.
- **La simplicité** : un dirigeant pressé doit comprendre un écran en 5 secondes. Aucun jargon, une action principale par écran, des chiffres lisibles en un coup d'œil.
- **La confiance** : on manipule l'argent et l'image de marque des clients. Le ton est sérieux, précis, affirmé — pas une startup gadget.
- **La validation** est le geste central : « Valider / Refuser » doit être évident, rapide, impossible à rater.

**L'univers visuel que je veux**
- Couleurs : un **bordeaux** profond comme couleur de marque, un **orange énergique** pour l'action et ce qui demande l'attention, un **marron terne** pour les fonds, les textes secondaires et le calme. Choisis toi-même les valeurs exactes et construis autour toute la palette nécessaire (neutres, fonds, bordures, textes, et des couleurs d'état succès / alerte / danger qui s'accordent avec cet univers chaud).
- **Aucune rondeur : que des angles.** Rayon de bordure à zéro partout — boutons, cartes, champs, badges, modales, avatars, graphiques. Des lignes nettes, une impression d'architecture.
- **Un peu d'italique**, utilisé avec intention : pour les titres éditoriaux, les accroches ou les chiffres clés — pas partout.
- **Une police originale**, qui donne une identité au premier regard. Interdites : Inter, Roboto, Open Sans, Lato, Poppins, Montserrat, Space Grotesk, DM Sans, et les polices système — tout ce qu'on voit sur mille outils. Propose-moi 3 associations (une police de titres avec du caractère et une vraie italique, une police de texte très lisible pour les chiffres et les tableaux), explique en une phrase ce que chacune raconte, et applique celle que tu recommandes. Elles doivent être libres d'usage commercial (Google Fonts, Fontshare ou licence libre), car je les réutiliserai dans des rapports PDF.

**Ça ne doit pas avoir l'air fait par une IA**
Pas de dégradés, pas de violet, pas d'effet verre dépoli, pas d'ombres douces partout, pas d'emojis ni d'icônes « étincelles », pas de grand titre centré sur fond dégradé, pas d'illustrations 3D génériques, pas de cartes toutes identiques alignées par trois. Je veux l'inverse : une mise en page éditoriale, assumée, avec de la hiérarchie et de l'asymétrie quand elle sert, des filets et des aplats francs, comme un magazine économique ou un cabinet de conseil qui a du goût. Chaque choix doit pouvoir se justifier.

**Ce que j'attends**
1. Une page **« Charte »** dans le projet qui présente :
   - la palette, avec le rôle de chaque couleur (à quoi elle sert, à quoi elle ne sert jamais) et les combinaisons texte/fond autorisées, toutes au contraste WCAG AA minimum ;
   - la typographie : les 3 associations proposées, celle retenue, l'échelle de tailles, les graisses, les règles d'usage de l'italique ;
   - la grille, les espacements, les règles d'angles et de bordures ;
   - les composants : boutons (principal, secondaire, danger), champs, cartes, tableaux, badges de gravité (critique / important / amélioration), note sur 100 en jauge, carte de validation avec Valider / Refuser, alertes, navigation latérale ;
   - les couleurs des graphiques (séries, positif/négatif) ;
   - le mode sombre ;
   - le ton des textes de l'interface : tutoiement, phrases courtes, zéro jargon, des exemples avant/après.
2. Les **design tokens** sous forme de variables CSS et de configuration Tailwind, prêts à être réutilisés ailleurs (je les reprendrai dans mes rapports PDF).
3. Trois écrans d'exemple qui appliquent la charte, avec des données réalistes inventées :
   - **le portefeuille du consultant** : ses marques, pour chacune les clients gagnés ce mois, le coût par client, et ce qui attend une validation ;
   - **un rapport d'audit** : note globale sur 100, trois piliers (Technique, On-Page, E-E-A-T) avec leur note, les problèmes classés par gravité avec « pourquoi » et « quoi faire » ;
   - **l'espace client** : ses résultats en haut, puis la file des contenus à valider.

Commence par la page Charte, puis les écrans. Desktop d'abord (le mobile viendra plus tard), en français.
