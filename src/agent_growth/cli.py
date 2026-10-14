"""Ligne de commande d'Agent Growth.

La console :

    ag serve                ouvrir la console multi-marques
    ag brand add <url>      enregistrer une marque
    ag brand list           lister les marques
    ag import-core <json>   enregistrer une marque depuis son brand-core.json
    ag tools                lister les outils branchables
    ag connect <outil> <réf> marquer un outil comme connecté

Les outils d'analyse :

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

from . import __version__, store
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


def cmd_serve(args: argparse.Namespace) -> int:
    """Ouvre la console. Elle lit la base, jamais les API directement."""
    import uvicorn

    from .console.app import create_app

    print(f"Console sur http://{args.host}:{args.port}  (base : {args.db})", file=sys.stderr)
    uvicorn.run(create_app(args.db), host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_brand_add(args: argparse.Namespace) -> int:
    conn = store.connect(args.db)
    slug = args.slug or slugify(args.url)
    if store.get_brand(conn, slug):
        print(f"✗ La marque « {slug} » existe déjà.", file=sys.stderr)
        return 1
    brand_id = store.add_brand(
        conn,
        slug=slug,
        name=args.name or slug,
        url=args.url,
        kind=args.kind,
        plan=args.plan,
        monthly_fee_eur=args.fee,
    )
    store.add_site(conn, brand_id, args.url, platform=args.platform)
    for kind in args.channel:
        store.add_channel(conn, brand_id, kind)
    store.log(conn, brand_id=brand_id, actor="humain", action="marque enregistrée",
              rationale=f"{len(args.channel)} canaux déclarés")
    print(f"✓ {slug} enregistrée ({len(args.channel)} canaux)", file=sys.stderr)
    print(f"  Prochaine étape : ag brand-core {args.url}", file=sys.stderr)
    return 0


def cmd_brand_list(args: argparse.Namespace) -> int:
    conn = store.connect(args.db)
    rows = store.portfolio(conn)
    if not rows:
        print("Aucune marque. Commence par : ag brand add <url>", file=sys.stderr)
        return 0
    for r in rows:
        b = r["brand"]
        fee = f"{b['monthly_fee_eur']:.0f} €/mois" if b["monthly_fee_eur"] else "—"
        print(f"{b['slug']:<24} {b['kind']:<8} {r['connected']}/{len(r['channels'])} canaux  "
              f"{fee:<12} {r['last_collected'] or 'jamais collecté'}")
    money = store.revenue(conn)
    print(f"\n{money['clients']} client(s) · {money['mrr']:.0f} €/mois", file=sys.stderr)
    return 0


def cmd_import_core(args: argparse.Namespace) -> int:
    conn = store.connect(args.db)
    brand_id = store.import_brand_core(conn, args.path)
    channels = store.list_channels(conn, brand_id)
    print(f"✓ marque enregistrée, {len(channels)} canaux déduits des angles : "
          f"{', '.join(c['kind'] for c in channels)}", file=sys.stderr)
    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    conn = store.connect(args.db)
    store.seed_catalog(conn)
    for row in store.list_integrations(conn, category=args.category):
        cfg = json.loads(row["config"] or "{}")
        mark = "✓" if row["state"] == "connecte" else " "
        print(f"{mark} {row['slug']:<18} {row['category']:<11} {cfg.get('gate', ''):<7} {row['name']}")
    return 0


def cmd_connect(args: argparse.Namespace) -> int:
    conn = store.connect(args.db)
    try:
        store.connect_integration(conn, args.tool, secret_ref=args.secret_ref)
    except (KeyError, ValueError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    store.log(conn, actor="humain", action=f"outil connecté : {args.tool}",
              rationale=f"référence {args.secret_ref}")
    print(f"✓ {args.tool} connecté (référence {args.secret_ref})", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ag",
        description="Agent Growth — le marketing digital d'une marque, piloté par sa ligne éditoriale.",
    )
    parser.add_argument("--version", action="version", version=f"agent-growth {__version__}")
    parser.add_argument("--db", default=str(store.DEFAULT_DB),
                        help=f"base de la console (défaut : {store.DEFAULT_DB})")
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

    # ---- la console ----------------------------------------------------- #
    serve = sub.add_parser("serve", help="ouvrir la console multi-marques")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=cmd_serve)

    brand = sub.add_parser("brand", help="gérer les marques")
    brand_sub = brand.add_subparsers(dest="brand_cmd", required=True)

    add = brand_sub.add_parser("add", help="enregistrer une marque")
    add.add_argument("url")
    add.add_argument("--name", help="nom affiché (défaut : le domaine)")
    add.add_argument("--slug", help="identifiant court (défaut : déduit du domaine)")
    add.add_argument("--kind", choices=("interne", "client"), default="interne",
                     help="« interne » pour tes propres marques, « client » pour une marque facturée")
    add.add_argument("--plan")
    add.add_argument("--fee", type=float, help="abonnement mensuel en euros")
    add.add_argument("--platform", default="inconnue",
                     choices=("wordpress", "shopify", "wix", "squarespace", "webflow",
                              "statique", "inconnue"))
    add.add_argument("--channel", action="append", default=[], metavar="CANAL",
                     choices=tuple(store.CHANNELS), help="canal actif (répétable)")
    add.set_defaults(func=cmd_brand_add)

    blist = brand_sub.add_parser("list", help="lister les marques")
    blist.set_defaults(func=cmd_brand_list)

    imp = sub.add_parser("import-core", help="enregistrer une marque depuis son brand-core.json")
    imp.add_argument("path")
    imp.set_defaults(func=cmd_import_core)

    tools = sub.add_parser("tools", help="lister les outils branchables")
    tools.add_argument("--category")
    tools.set_defaults(func=cmd_tools)

    conn_p = sub.add_parser("connect", help="marquer un outil comme connecté")
    conn_p.add_argument("tool")
    conn_p.add_argument("secret_ref",
                        help="NOM de la variable d'environnement ou clé de coffre — jamais le secret")
    conn_p.set_defaults(func=cmd_connect)

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
