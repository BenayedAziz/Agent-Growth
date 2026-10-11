"""Ligne de commande d'Agent Growth.

    ag brand-core <url>     construire la ligne éditoriale de la marque
    ag inspect <url>        voir ce que l'agent lit du site (gratuit, sans IA)
    ag render <json>        régénérer les documents depuis un brand-core.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from . import __version__
from .crawl import crawl_site
from .llm import LlmError
from .render import to_markdown, to_voice
from .schemas import BrandCoreDocument
from .tools import brand_core

BRANDS_DIR = Path("brands")


def slugify(url: str) -> str:
    host = re.sub(r"^https?://", "", url).split("/")[0]
    host = re.sub(r"^www\.", "", host)
    ascii_host = unicodedata.normalize("NFKD", host).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_host.lower()).strip("-") or "marque"


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def cmd_inspect(args: argparse.Namespace) -> int:
    """Montre exactement ce que l'agent voit. Aucun appel au modèle, donc gratuit."""
    pages = crawl_site(args.url, max_pages=args.max_pages)
    for page in pages:
        print(f"\n[{page.role}] {page.url}")
        if page.error:
            print(f"  ⚠ {page.error}")
            continue
        seo = page.seo
        assert seo is not None
        print(f"  title ({seo.title_length}) : {seo.title or '(absent)'}")
        print(f"  meta  ({seo.meta_description_length}) : {seo.meta_description or '(absente)'}")
        print(f"  H1 : {' | '.join(seo.h1) or '(aucun)'}")
        print(f"  {seo.word_count} mots · {seo.internal_link_count} liens internes · "
              f"lang={seo.lang or '?'} · JSON-LD={'oui' if seo.has_structured_data else 'non'}")
    print(f"\n{len(pages)} page(s) lue(s).")
    return 0


def cmd_brand_core(args: argparse.Namespace) -> int:
    notes = args.notes or ""
    if args.notes_file:
        notes = Path(args.notes_file).read_text(encoding="utf-8")

    if args.dry_run:
        # Permet de relire et d'ajuster ce qu'on envoie, sans dépenser un euro.
        pages = crawl_site(args.url, max_pages=args.max_pages)
        print(brand_core.build_prompt(args.url, pages, [], notes))
        return 0

    out_dir = Path(args.out) if args.out else BRANDS_DIR / slugify(args.url)
    print(f"Lecture de {args.url}…", file=sys.stderr)

    try:
        doc = brand_core.run(
            args.url,
            competitors=args.competitor,
            max_pages=args.max_pages,
            notes=notes,
        )
    except LlmError as exc:
        print(f"\n✗ {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"\n✗ {exc}", file=sys.stderr)
        return 1

    written = [
        _write(out_dir / "brand-core.json", json.dumps(doc.model_dump(), ensure_ascii=False, indent=2) + "\n"),
        _write(out_dir / "brand-core.md", to_markdown(doc)),
        _write(out_dir / "voice.md", to_voice(doc)),
    ]

    print(f"\n✓ {doc.core.brand_name} — {len(doc.core.opportunities)} opportunités chiffrées", file=sys.stderr)
    for path in written:
        print(f"  {path}", file=sys.stderr)
    print("\nÀ lire en premier : " + str(out_dir / "brand-core.md"), file=sys.stderr)
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    source = Path(args.path)
    doc = BrandCoreDocument.model_validate_json(source.read_text(encoding="utf-8"))
    out_dir = Path(args.out) if args.out else source.parent
    print(_write(out_dir / "brand-core.md", to_markdown(doc)))
    print(_write(out_dir / "voice.md", to_voice(doc)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ag",
        description="Agent Growth — le marketing digital d'une marque, piloté par sa ligne éditoriale.",
    )
    parser.add_argument("--version", action="version", version=f"agent-growth {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    core = sub.add_parser("brand-core", help="construire la ligne éditoriale de la marque")
    core.add_argument("url", help="adresse du site de la marque")
    core.add_argument("--competitor", action="append", default=[], metavar="URL",
                      help="site d'un concurrent (répétable)")
    core.add_argument("--max-pages", type=int, default=6, help="pages du site à lire (défaut : 6)")
    core.add_argument("--notes", help="ce que le dirigeant nous a dit, en texte libre")
    core.add_argument("--notes-file", help="fichier contenant ces notes")
    core.add_argument("--out", help="dossier de sortie (défaut : brands/<nom-de-domaine>)")
    core.add_argument("--dry-run", action="store_true",
                      help="afficher le prompt sans appeler le modèle (gratuit)")
    core.set_defaults(func=cmd_brand_core)

    inspect = sub.add_parser("inspect", help="voir ce que l'agent lit du site, sans appeler l'IA")
    inspect.add_argument("url")
    inspect.add_argument("--max-pages", type=int, default=6)
    inspect.set_defaults(func=cmd_inspect)

    render = sub.add_parser("render", help="régénérer les documents depuis un brand-core.json")
    render.add_argument("path", help="chemin du brand-core.json")
    render.add_argument("--out", help="dossier de sortie (défaut : celui du JSON)")
    render.set_defaults(func=cmd_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrompu.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
