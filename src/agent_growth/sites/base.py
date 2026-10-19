"""L'interface commune aux adaptateurs."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Literal, Protocol

#: Marqueur lisible par machine ajouté à tout contenu généré qui part en ligne
#: (article 50 de l'AI Act, ADR-011). Un seul endroit le définit.
#: Forme exacte à faire valider par un juriste avant tout engagement client.
AI_MARK_HTML = "<!-- ai-generated: true; tool: agent-growth -->"


@dataclass
class Change:
    id: int
    kind: Literal["page_create", "page_update"]
    title: str
    body: str
    target: str = ""
    slug: str = ""
    meta: dict = field(default_factory=dict)
    ai_generated: bool = True

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Change":
        return cls(
            id=int(row["id"]), kind=row["kind"], title=row["title"], body=row["body"],
            target=row["target"], slug=row["slug"] or slugify(row["title"]),
            meta=json.loads(row["meta"] or "{}"), ai_generated=bool(row["ai_generated"]),
        )

    def marked_body(self) -> str:
        if not self.ai_generated or AI_MARK_HTML in self.body:
            return self.body
        return f"{self.body}\n{AI_MARK_HTML}"


@dataclass
class Applied:
    ok: bool
    state: Literal["applique", "manuel", "echec"]
    detail: str
    url: str = ""


class Adapter(Protocol):
    name: str

    def apply(self, change: Change) -> Applied: ...


def slugify(text: str) -> str:
    import unicodedata

    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:80] or "page"
