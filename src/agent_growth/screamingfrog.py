"""Import d'un crawl Screaming Frog SEO Spider.

Notre robot lit jusqu'à quelques dizaines de pages : assez pour un premier
audit, pas pour un site de 2 000 fiches produits. Screaming Frog lit tout,
rend le JavaScript, et c'est l'outil de référence que le client ou son
développeur connaît déjà. On ne le réécrit pas (règle 6) : on lit son export
et on lui applique nos règles, pour garder un seul rapport.

Ce qu'on importe : l'onglet **Internal → All** exporté en CSV, depuis
l'interface (bouton *Export*) ou en ligne de commande :

    screamingfrogseospider --crawl https://site.fr --headless \\
        --output-folder ./sf --export-tabs "Internal:All" --overwrite

Les colonnes sont lues par leur nom anglais : l'interface de Screaming Frog
doit être en anglais au moment de l'export.

Ce que Screaming Frog couvre remplace notre crawl pour les règles de titres,
descriptions, H1, contenu, canonique, indexation et erreurs. Le reste — données
structurées, coordonnées, pages de confiance, vitesse — vient toujours de nos
propres lectures.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
from pathlib import Path

from .crawl import Page, SeoSignals

#: Les règles d'audit que l'export Screaming Frog suffit à appliquer.
COVERED = frozenset({
    "pages-cassees", "title-absent", "title-court", "title-long", "title-duplique",
    "meta-absente", "meta-dupliquee", "h1-absent", "h1-multiple", "h1-casse",
    "contenu-mince", "canonical-absente", "noindex", "page-brouillon", "page-doublon",
})

REQUIRED = ("Address", "Content Type", "Status Code")


def _read_rows(text: str) -> list[dict[str, str]]:
    lines = text.lstrip("﻿").splitlines()
    # Les anciennes versions ajoutent une ligne de titre (« Internal - All »)
    # avant les en-têtes.
    start = next((i for i, line in enumerate(lines[:5]) if '"Address"' in line or line.startswith("Address")), 0)
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(
            f"Export Screaming Frog non reconnu : colonnes {', '.join(missing)} absentes. "
            "Exporter l'onglet « Internal → All » avec l'interface en anglais."
        )
    return list(reader)


def _int(value: str) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


def load(path: str | Path) -> list[Page]:
    """Export CSV « Internal: All » → pages au format de notre crawler.

    Seules les pages HTML comptent. Les redirections sont ignorées : la page
    d'arrivée figure déjà dans l'export.
    """
    path = Path(path)
    if path.is_dir():
        path = path / "internal_all.csv"
    rows = _read_rows(path.read_text(encoding="utf-8", errors="replace"))
    pages: list[Page] = []
    for row in rows:
        if "html" not in row.get("Content Type", "").lower() and _int(row.get("Status Code", "")) < 400:
            continue
        url, status = row["Address"], _int(row.get("Status Code", ""))
        if 300 <= status < 400:
            continue
        if status >= 400 or status == 0:
            pages.append(Page(url=url, status=status, role="page", text="", error=row.get("Status", "HTTP error")))
            continue
        title = row.get("Title 1", "")
        meta = row.get("Meta Description 1", "")
        h1 = [row[k] for k in ("H1-1", "H1-2") if row.get(k)]
        robots = f"{row.get('Meta Robots 1', '')} {row.get('X-Robots-Tag 1', '')}".lower()
        pages.append(Page(url=url, status=status, role="page", text="", seo=SeoSignals(
            title=title, title_length=len(title),
            meta_description=meta, meta_description_length=len(meta),
            h1=h1, h2=[row[k] for k in ("H2-1", "H2-2") if row.get(k)],
            lang="", canonical=row.get("Canonical Link Element 1", ""), og_tags=[],
            has_structured_data=False, word_count=_int(row.get("Word Count", "")),
            internal_link_count=_int(row.get("Unique Outlinks", "")),
            noindex="noindex" in robots,
        )))
    return pages


def crawl(url: str, out_dir: str | Path) -> Path:
    """Lance Screaming Frog en ligne de commande, s'il est installé, et renvoie
    le chemin de l'export. `AG_SCREAMINGFROG` désigne l'exécutable."""
    binary = shutil.which(os.environ.get("AG_SCREAMINGFROG", "screamingfrogseospider"))
    if not binary:
        raise FileNotFoundError(
            "Screaming Frog n'est pas installé ici. Lancer le crawl sur l'ordinateur où il l'est, "
            "exporter « Internal → All » en CSV, puis : ag audit URL --screaming-frog fichier.csv"
        )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([binary, "--crawl", url, "--headless", "--output-folder", str(out),
                    "--export-tabs", "Internal:All", "--overwrite"], check=True, timeout=3 * 3600)
    return out / "internal_all.csv"
