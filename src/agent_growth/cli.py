"""Ligne de commande d'Agent Growth.

La console :

    ag run                  production : console + planificateur + Telegram
    ag serve                ouvrir la console en local (sans tâches automatiques)
    ag site add <marque> <url>   brancher un site (WordPress, Shopify, sur mesure…)
    ag site propose <site>  proposer une page (validation requise avant écriture)
    ag brand add <url>      enregistrer une marque
    ag brand list           lister les marques
    ag import-core <json>   enregistrer une marque depuis son brand-core.json
    ag tools                lister les outils branchables
    ag connect <outil> <réf> marquer un outil comme connecté

Les outils d'analyse :

    ag audit <url>          audit SEO / GEO complet du site (gratuit, sans IA)
    ag audit-report <dossier>  refaire le rapport après la recherche Google manuelle
    ag mots-cles <dossier>  mots-clés, concurrents et écart via DataForSEO (≈ 0,20 $)
    ag brand-core <url>     construire la ligne éditoriale de la marque
    ag inspect <url>        voir ce que l'agent lit du site (gratuit, sans IA)
    ag render <json>        régénérer les documents depuis un brand-core.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

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


def cmd_audit(args: argparse.Namespace) -> int:
    """Audit SEO / GEO. Règles vérifiables, aucun appel au modèle : gratuit et
    reproductible. Écrit le rapport client dans `--out`."""
    from . import audit, dataforseo, semantics

    source = " + export Screaming Frog" if args.screaming_frog else ""
    print(f"Audit de {args.url} (jusqu'à {args.max_pages} pages{source})…", file=sys.stderr)
    result = audit.run(args.url, max_pages=args.max_pages, speed=not args.no_speed,
                       screaming_frog=args.screaming_frog)
    conn = store.connect(args.db)
    brand_id = None
    if args.brand:
        brand = store.get_brand(conn, args.brand)
        if brand is None:
            print(f"✗ Marque inconnue : {args.brand}", file=sys.stderr)
            return 1
        brand_id = int(brand["id"])
    store.save_audit(conn, result, brand_id=brand_id)

    data = {**result.to_dict(), "brand": args.name or ""}
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    host = urlparse(result.url).netloc.removeprefix("www.")
    out = Path(args.out) if args.out else Path("brands") / host / "audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    manual_path = out / "recherche-manuelle.json"
    if not manual_path.exists():
        manual_path.write_text(json.dumps(audit.manual_checklist(result.url, brand=args.name or ""),
                                          ensure_ascii=False, indent=2), encoding="utf-8")
    keywords_path = out / "mots-cles.json"
    if not keywords_path.exists():
        keywords_path.write_text(json.dumps(semantics.keyword_template(), ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    if dataforseo.available() and not args.no_keywords:
        try:
            _fetch_keywords(out, market=args.marche, competitors=args.concurrent)
        except dataforseo.DataForSEOError as exc:
            print(f"⚠ {exc} — relancer ensuite : ag mots-cles {out}", file=sys.stderr)
    report = _write_report(out)

    c = result.counts
    print(f"\n{result.url} — note {result.score}/100 — {data['pages']} pages analysées")
    print(f"{c['critique']} critique(s) · {c['important']} important(s) · {c['amelioration']} amélioration(s)")
    for pillar in report["pillars"]:
        print(f"  {pillar['label']:<10} {pillar['score']:>3}/100 · {len(pillar['findings'])} constat(s) · "
              f"{len(pillar['passed'])} point(s) acquis")
    for s in result.speed:
        verdict = f"note {s.score}/100 ({s.source})" if not s.error else f"⚠ {s.error}"
        print(f"  vitesse {s.strategy:<7} {s.url} : {verdict}")
    print(f"\nRapport : {out / 'rapport.html'}")
    if report["draft"]:
        print(f"Version de travail : {len(report['pending'])} point(s) à compléter :")
        for item in report["pending"]:
            print(f"  · {item['question']}")
        print(f"Puis : ag audit-report {out}\n"
              f"(Mots-clés du consultant : {keywords_path} · export Search Console : {out}/search-console.zip)")
    return 0


def _write_report(folder: Path) -> dict:
    """Refait `rapport.html` à partir de ce que contient le dossier de l'audit :
    audit.json, recherche-manuelle.json, mots-cles.json, et l'export Search
    Console s'il y est (search-console.zip ou search-console.csv)."""
    from . import audit, render, semantics

    def read(name: str):
        path = folder / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    data = read("audit.json")
    market = read("semantique.json")
    console = next((folder / n for n in ("search-console.zip", "search-console.csv") if (folder / n).exists()), None)
    report = audit.report(data, read("recherche-manuelle.json"), brand=data.get("brand", ""),
                          keywords=read("mots-cles.json"),
                          search_console=semantics.load_search_console(console) if console else None,
                          market=market)
    (folder / "rapport.html").write_text(render.audit_html(report), encoding="utf-8")
    return report


def _fetch_keywords(folder: Path, *, market: str = "fr", competitors: list[str] | None = None) -> dict:
    """Interroge DataForSEO et écrit `semantique.json` dans le dossier de l'audit."""
    from . import dataforseo

    data = json.loads((folder / "audit.json").read_text(encoding="utf-8"))
    path = folder / "mots-cles.json"
    keywords = [k["mot_cle"].strip() for k in (json.loads(path.read_text(encoding="utf-8")) if path.exists() else [])
                if k.get("mot_cle", "").strip()]
    print(f"Mots-clés et concurrents (DataForSEO, marché {market})…", file=sys.stderr)
    result = dataforseo.analyse(data["url"], keywords, market=market, competitors=competitors)
    (folder / "semantique.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {len(result['ranked'])} mot(s)-clé(s) positionné(s) · {len(result['competitors'])} concurrent(s) · "
          f"{len(result['gap'])} recherche(s) de concurrents absentes du site · coût {result['cost_usd']} $",
          file=sys.stderr)
    return result


def cmd_keywords(args: argparse.Namespace) -> int:
    """(Re)lance l'analyse des mots-clés d'un audit, puis refait le rapport."""
    from . import dataforseo

    folder = Path(args.folder)
    if not (folder / "audit.json").exists():
        print(f"✗ Pas d'audit dans {folder}. Lancer d'abord : ag audit URL", file=sys.stderr)
        return 1
    try:
        _fetch_keywords(folder, market=args.marche, competitors=args.concurrent)
    except dataforseo.DataForSEOError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    return cmd_audit_report(args)


def cmd_audit_report(args: argparse.Namespace) -> int:
    """Refait le rapport d'un audit déjà lancé, après la recherche manuelle."""
    folder = Path(args.folder)
    if not (folder / "audit.json").exists():
        print(f"✗ Pas d'audit dans {folder} (audit.json absent). Lancer d'abord : ag audit URL", file=sys.stderr)
        return 1
    report = _write_report(folder)
    print(f"Rapport : {folder / 'rapport.html'}")
    if report["draft"]:
        print(f"Encore {len(report['pending'])} vérification(s) manuelle(s) à remplir : version de travail.")
    else:
        print("Prêt à envoyer.")
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


LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def cmd_serve(args: argparse.Namespace) -> int:
    """Ouvre la console en local, sans tâches automatiques."""
    import uvicorn

    from .console.app import create_app

    password = os.environ.get("AG_CONSOLE_PASSWORD") or None
    if args.host not in LOOPBACK and not password:
        print("✗ Console exposée sans mot de passe : définis AG_CONSOLE_PASSWORD.", file=sys.stderr)
        return 2
    print(f"Console sur http://{args.host}:{args.port}  (base : {args.db})", file=sys.stderr)
    uvicorn.run(create_app(args.db, password=password), host=args.host, port=args.port,
                log_level="warning")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """La production : console, planificateur et Telegram dans un seul service.

    Un seul processus, parce que la base est SQLite : deux répliques écriraient
    chacune de leur côté. Sur Railway, garder une seule instance.
    """
    import logging

    import uvicorn

    from .autonomy import scheduler, telegram
    from .console.app import create_app

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    password = os.environ.get("AG_CONSOLE_PASSWORD") or None
    if args.host not in LOOPBACK and not password:
        # Refus dur : une console ouverte sur Internet permettrait à n'importe
        # qui de valider une dépense.
        print("✗ AG_CONSOLE_PASSWORD manquant. La console ne démarre pas exposée sans mot de passe.",
              file=sys.stderr)
        return 2

    bot = telegram.from_env()
    if bot is None:
        print("! TELEGRAM_BOT_TOKEN absent : validations par la console uniquement.", file=sys.stderr)
    elif bot.owner_id is None:
        print("! TELEGRAM_OWNER_ID absent : envoie /start au bot pour obtenir ton identifiant.",
              file=sys.stderr)

    ctx = scheduler.Context(db_path=Path(args.db), telegram=bot)
    port = args.port or int(os.environ.get("PORT", "8000"))
    print(f"Agent Growth sur {args.host}:{port} — base {args.db}", file=sys.stderr)
    uvicorn.run(create_app(args.db, password=password, worker=ctx,
                           user=os.environ.get("AG_CONSOLE_USER", "admin")),
                host=args.host, port=port, log_level="info", proxy_headers=True)
    return 0


def cmd_site_add(args: argparse.Namespace) -> int:
    conn = store.connect(args.db)
    brand = store.get_brand(conn, args.brand)
    if brand is None:
        print(f"✗ Marque inconnue : {args.brand}. Voir « ag brand list ».", file=sys.stderr)
        return 1
    config = {}
    for item in args.config:
        key, _, value = item.partition("=")
        config[key.strip()] = value.strip()
    try:
        site_id = store.add_site(conn, int(brand["id"]), args.url, platform=args.platform,
                                 secret_ref=args.secret_ref or "", config=config)
    except ValueError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    site = store.get_site(conn, site_id)
    mode = {"api": "écriture par API", "git": "pull request GitHub",
            "manuel": "dossier prêt à coller", "aucun": "lecture seule"}[site["write_access"]]
    print(f"✓ site n°{site_id} — {args.platform} — {mode}", file=sys.stderr)
    if args.secret_ref and not os.environ.get(args.secret_ref):
        print(f"! La variable {args.secret_ref} n'est pas définie ici. Ajoute-la dans Railway.",
              file=sys.stderr)
    return 0


def cmd_site_propose(args: argparse.Namespace) -> int:
    conn = store.connect(args.db)
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else (args.body or "")
    try:
        change_id, approval_id = store.propose_site_change(
            conn, args.site, kind="page_update" if args.target else "page_create",
            title=args.title, body=body, target=args.target or "",
            meta={"description": args.description} if args.description else None,
        )
    except KeyError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    if approval_id is None:
        print(f"✓ modification n°{change_id} validée automatiquement (règle active)", file=sys.stderr)
    else:
        print(f"✓ modification n°{change_id} en attente de validation (demande n°{approval_id})",
              file=sys.stderr)
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
    parser.add_argument("--db", default=os.environ.get("AG_DB", str(store.DEFAULT_DB)),
                        help=f"base de la console (défaut : $AG_DB, sinon {store.DEFAULT_DB})")
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

    aud = sub.add_parser("audit", help="audit SEO / GEO complet du site (gratuit, sans IA)")
    aud.add_argument("url")
    aud.add_argument("--max-pages", type=int, default=40)
    aud.add_argument("--brand", help="rattacher l'audit à une marque (suivi dans le temps)")
    aud.add_argument("--json", action="store_true", help="sortie JSON")
    aud.add_argument("--name", help="nom de la marque, affiché sur le rapport")
    aud.add_argument("--out", help="dossier du rapport (défaut : brands/<domaine>/audit)")
    aud.add_argument("--screaming-frog", metavar="CSV",
                     help="export « Internal: All » de Screaming Frog, pour un crawl complet")
    aud.add_argument("--no-speed", action="store_true", help="ne pas mesurer la vitesse")
    aud.add_argument("--marche", default="fr", choices=["fr", "be", "ch", "ca", "ma", "tn", "us", "uk"],
                     help="pays dont on étudie les recherches Google (défaut : fr)")
    aud.add_argument("--concurrent", action="append",
                     help="domaine concurrent à comparer (répétable ; sinon trouvés automatiquement)")
    aud.add_argument("--no-keywords", action="store_true", help="ne pas interroger DataForSEO")
    aud.set_defaults(func=cmd_audit)

    kw = sub.add_parser("mots-cles", help="mots-clés, concurrents et écart (DataForSEO) d'un audit")
    kw.add_argument("folder", help="dossier de l'audit (celui qui contient audit.json)")
    kw.add_argument("--marche", default="fr", choices=["fr", "be", "ch", "ca", "ma", "tn", "us", "uk"])
    kw.add_argument("--concurrent", action="append", help="domaine concurrent (répétable)")
    kw.set_defaults(func=cmd_keywords)

    rep = sub.add_parser("audit-report", help="refaire le rapport client après la recherche manuelle")
    rep.add_argument("folder", help="dossier de l'audit (celui qui contient audit.json)")
    rep.set_defaults(func=cmd_audit_report)

    inspect = sub.add_parser("inspect", help="voir ce que l'agent lit du site, sans appeler l'IA")
    inspect.add_argument("url")
    inspect.add_argument("--max-pages", type=int, default=6)
    inspect.set_defaults(func=cmd_inspect)

    render = sub.add_parser("render", help="régénérer les documents depuis un brand-core.json")
    render.add_argument("path", help="chemin du brand-core.json")
    render.add_argument("--out", help="dossier de sortie (défaut : celui du JSON)")
    render.set_defaults(func=cmd_render)

    # ---- la console ----------------------------------------------------- #
    run = sub.add_parser("run", help="production : console + planificateur + Telegram")
    run.add_argument("--host", default="0.0.0.0")
    run.add_argument("--port", type=int, default=0, help="défaut : $PORT, sinon 8000")
    run.set_defaults(func=cmd_run)

    site = sub.add_parser("site", help="brancher et modifier les sites")
    site_sub = site.add_subparsers(dest="site_cmd", required=True)
    sadd = site_sub.add_parser("add", help="brancher un site")
    sadd.add_argument("brand", help="identifiant de la marque (voir ag brand list)")
    sadd.add_argument("url")
    sadd.add_argument("--platform", required=True, choices=tuple(store.PLATFORMS))
    sadd.add_argument("--secret-ref", help="NOM de la variable qui porte l'accès (jamais la valeur)")
    sadd.add_argument("--config", action="append", default=[], metavar="CLÉ=VALEUR",
                      help="ex. user=admin, shop=x.myshopify.com, repo=moi/site, dir=content/pages")
    sadd.set_defaults(func=cmd_site_add)

    sprop = site_sub.add_parser("propose", help="proposer une page ; rien n'est écrit avant validation")
    sprop.add_argument("site", type=int, help="numéro du site")
    sprop.add_argument("--title", required=True)
    sprop.add_argument("--body")
    sprop.add_argument("--body-file")
    sprop.add_argument("--target", help="page existante à modifier (identifiant ou chemin)")
    sprop.add_argument("--description", help="meta description")
    sprop.set_defaults(func=cmd_site_propose)

    serve = sub.add_parser("serve", help="ouvrir la console en local, sans tâches automatiques")
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
