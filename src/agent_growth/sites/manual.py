"""Les plateformes sans API d'écriture : SpeedMedia, Wix, Squarespace…

On prépare un dossier prêt à coller — titre, adresse, texte, balises — et on
prévient l'humain. « Voilà exactement quoi faire » vaut mieux qu'une écriture à
l'aveugle, et ça reste une heure gagnée sur la rédaction.
"""

from __future__ import annotations

from pathlib import Path

from .base import Applied, Change

WHERE = {
    "speedmedia": "l'administration SpeedMedia (gestion des pages et des modules)",
    "wix": "l'éditeur Wix",
    "squarespace": "l'éditeur Squarespace",
    "webflow": "le Designer Webflow",
}


class ManualAdapter:
    name = "manuel"

    def __init__(self, directory: Path, *, platform: str, site_url: str):
        self.directory = directory
        self.platform = platform
        self.site_url = site_url

    def apply(self, change: Change) -> Applied:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{change.id:05d}-{change.slug}.md"
        where = WHERE.get(self.platform, "l'administration du site")
        action = "Créer une nouvelle page" if change.kind == "page_create" else f"Modifier la page {change.target}"
        description = change.meta.get("description", "")

        path.write_text(
            "\n".join([
                f"# À appliquer sur {self.site_url}",
                "",
                f"**Où** : {where}",
                f"**Action** : {action}",
                "",
                "## Titre de la page",
                change.title,
                "",
                "## Adresse (slug)",
                change.slug,
                "",
                *(["## Meta description", description, ""] if description else []),
                "## Contenu à coller",
                "",
                change.marked_body(),
                "",
                "---",
                "Une fois en ligne, réponds « fait » dans la console pour clôturer.",
            ]),
            encoding="utf-8",
        )
        return Applied(True, "manuel", f"Prêt à coller dans {where} : {path.name}", url=str(path))
