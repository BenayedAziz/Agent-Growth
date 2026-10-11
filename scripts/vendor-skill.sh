#!/usr/bin/env bash
# Copie une skill publiée sur GitHub dans skills/vendor/<nom>/ et épingle son commit.
#
#   ./scripts/vendor-skill.sh https://github.com/auteur/depot-skill ig
#
# On copie au lieu de dépendre : une skill est faite d'instructions que Claude
# suit et de scripts qu'il exécute. Un sous-module laisserait ce code changer
# sous nos pieds, donc changer le comportement du produit sans décision de notre
# part.
#
# ⚠ Rien n'est activé par ce script. Lis chaque SKILL.md et chaque script avant
#   de t'en servir — voir docs/ARCHITECTURE.md#brancher-une-skill-externe.
set -euo pipefail

if [ $# -lt 2 ]; then
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 64
fi

repo_url=$1
name=$2
dest="skills/vendor/$name"

if [ -e "$dest" ]; then
  echo "✗ $dest existe déjà. Supprime-le d'abord si tu veux le remplacer." >&2
  exit 1
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "→ Clone de $repo_url"
git clone --depth 1 "$repo_url" "$tmp/src" >/dev/null 2>&1
commit=$(git -C "$tmp/src" rev-parse HEAD)

if [ ! -d "$tmp/src/skills" ]; then
  echo "✗ Pas de dossier skills/ dans ce dépôt. Copie les fichiers utiles à la main." >&2
  exit 1
fi

mkdir -p "$dest"
cp -R "$tmp/src/skills/." "$dest/"
for extra in templates README.md LICENSE; do
  [ -e "$tmp/src/$extra" ] && cp -R "$tmp/src/$extra" "$dest/"
done

license=$( [ -f "$dest/LICENSE" ] && head -3 "$dest/LICENSE" | tr '\n' ' ' || echo "non trouvée — à vérifier" )

cat > "$dest/VENDOR.md" <<VENDOR
# Origine de cette skill

- **Dépôt** : $repo_url
- **Commit épinglé** : \`$commit\`
- **Copié le** : $(date -u +%Y-%m-%d)
- **Licence** : $license

## Statut

⬜ Pas encore relue. **Ne pas activer avant relecture.**

## Relecture (à cocher)

- [ ] Chaque \`SKILL.md\` lu : rien qui sorte du projet, appelle le réseau ou
      contourne une validation humaine
- [ ] Chaque script lu : réseau, disque, dépendances
- [ ] Licence compatible avec un usage commercial
- [ ] Limites annoncées par l'auteur relevées ici :

## Modifications locales

Aucune pour l'instant. Toute modification se note ici, sinon la prochaine mise
à jour l'écrasera sans qu'on s'en aperçoive.

## Mise à jour

\`\`\`bash
rm -rf $dest && ./scripts/vendor-skill.sh $repo_url $name
\`\`\`

Puis relire le diff : c'est là que des instructions peuvent avoir changé.
VENDOR

echo "✓ $dest  (commit $commit)"
echo "  → Lis $dest/VENDOR.md avant d'activer quoi que ce soit."
