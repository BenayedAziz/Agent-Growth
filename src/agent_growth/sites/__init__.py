"""Écrire sur le vrai site du client, quelle que soit sa plateforme.

C'est la seule pièce logicielle qu'aucune librairie de skills ne fournit
(ADR-009) : elle demande des accès, un adaptateur par plateforme et une
responsabilité. Rien n'est écrit sans validation préalable (`site_change` en
état `approuve`).

Un adaptateur par fichier, derrière la même interface : quand une plateforme
change ses règles, un seul fichier casse.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import httpx2 as httpx

from .base import Adapter, Applied, Change, slugify
from .github import GitHubAdapter
from .manual import ManualAdapter
from .shopify import ShopifyAdapter
from .wordpress import WordPressAdapter

__all__ = ["Adapter", "Applied", "Change", "adapter_for"]


class MissingAccess(RuntimeError):
    """Le site n'a pas d'accès configuré : on bascule en mode manuel."""


def adapter_for(
    site: sqlite3.Row,
    *,
    brand_slug: str,
    pack_dir: Path,
    client: httpx.Client | None = None,
    env: dict[str, str] | None = None,
) -> Adapter:
    """Choisit l'adaptateur d'un site. Sans accès d'écriture, c'est le mode
    manuel : on prépare tout, l'humain colle. Mieux vaut « voilà exactement quoi
    faire » qu'une écriture à l'aveugle."""
    env = os.environ if env is None else env
    config = json.loads(site["config"] or "{}")
    secret = env.get(site["secret_ref"], "") if site["secret_ref"] else ""
    # L'identifiant de marque devient un nom de dossier : on le nettoie, pour
    # qu'aucune valeur (« ../.. ») ne fasse écrire hors du dossier prévu.
    manual = ManualAdapter(pack_dir / slugify(brand_slug), platform=site["platform"], site_url=site["url"])

    if not secret:
        return manual
    if site["platform"] == "wordpress":
        return WordPressAdapter(site["url"], user=config.get("user", ""), app_password=secret,
                                status=config.get("status", "draft"), client=client)
    if site["platform"] == "shopify":
        return ShopifyAdapter(config.get("shop", ""), token=secret,
                              api_version=config.get("api_version", "2026-07"),
                              publish=bool(config.get("publish", False)), client=client)
    if site["platform"] == "sur_mesure":
        return GitHubAdapter(config.get("repo", ""), token=secret,
                             base=config.get("base", "main"),
                             directory=config.get("dir", "content/pages"),
                             extension=config.get("ext", ".md"), client=client)
    return manual
