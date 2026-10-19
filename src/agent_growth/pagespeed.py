"""Vitesse des pages, mesurée par Google PageSpeed Insights.

On ne mesure pas la vitesse nous-mêmes : un chiffre sorti de notre serveur ne
convaincrait personne. PageSpeed Insights est l'outil public de Google, que le
client peut relancer lui-même pour vérifier. Il donne deux choses :

- **les données terrain** (rapport Chrome UX) : ce qu'ont vécu les vrais
  visiteurs du site sur 28 jours. Elles n'existent que pour les sites assez
  fréquentés — sinon on le dit, on ne les remplace pas ;
- **les données labo** (Lighthouse) : un chargement simulé, avec une note sur
  100 et les pistes d'accélération.

L'API est gratuite. Sans clé, elle partage un quota commun souvent épuisé :
une clé (`PAGESPEED_API_KEY`, gratuite dans Google Cloud) évite les refus.

Si l'API refuse quand même, on lance **Lighthouse** nous-mêmes : c'est le
moteur que PageSpeed Insights fait tourner chez Google, avec les mêmes règles
et les mêmes notes. On perd seulement les données terrain, qui n'existent que
chez Google. La source est toujours indiquée dans le rapport.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Literal

import httpx2 as httpx

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
TIMEOUT = 120.0

Strategy = Literal["mobile", "desktop"]
Source = Literal["pagespeed", "lighthouse", ""]

#: Seuils publiés par Google pour les Core Web Vitals (75ᵉ centile).
CWV_GOOD = {"lcp_ms": 2500, "inp_ms": 200, "cls": 0.1}


@dataclass
class Speed:
    url: str
    strategy: Strategy
    score: int | None = None            # note labo sur 100
    lcp_ms: float | None = None         # labo : affichage du contenu principal
    cls: float | None = None            # labo : stabilité de la mise en page
    tbt_ms: float | None = None         # labo : temps où la page ne répond pas
    field_data: dict = field(default_factory=dict)   # terrain : {lcp_ms, inp_ms, cls, category}
    field_scope: str = ""               # "page", "site" ou "" (pas de données terrain)
    opportunities: list[dict] = field(default_factory=list)  # [{title, savings_ms}]
    source: Source = ""
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def cwv_passed(self) -> bool | None:
        """Verdict Google sur les visiteurs réels ; None sans données terrain."""
        if not self.field_data:
            return None
        return self.field_data.get("category") == "FAST"


def _field(experience: dict) -> dict:
    metrics = experience.get("metrics") or {}

    def p(name: str) -> float | None:
        value = (metrics.get(name) or {}).get("percentile")
        return float(value) if value is not None else None

    cls = p("CUMULATIVE_LAYOUT_SHIFT_SCORE")   # l'API le donne multiplié par 100
    out = {
        "lcp_ms": p("LARGEST_CONTENTFUL_PAINT_MS"),
        "inp_ms": p("INTERACTION_TO_NEXT_PAINT"),
        "cls": cls / 100 if cls is not None else None,
        "category": experience.get("overall_category", ""),
    }
    return out if any(v is not None for k, v in out.items() if k != "category") else {}


def parse(url: str, strategy: Strategy, data: dict) -> Speed:
    """Réponse de l'API → `Speed`. Séparé de l'appel pour être testé sur un fixture."""
    lh = data.get("lighthouseResult") or {}
    audits = lh.get("audits") or {}
    perf = ((lh.get("categories") or {}).get("performance") or {}).get("score")

    def num(key: str) -> float | None:
        value = (audits.get(key) or {}).get("numericValue")
        return round(float(value), 3) if value is not None else None

    opportunities = []
    for audit in audits.values():
        details = audit.get("details") or {}
        if details.get("type") != "opportunity":
            continue
        savings = details.get("overallSavingsMs")
        if savings is None:
            savings = max((audit.get("metricSavings") or {}).values(), default=0)
        if savings and savings >= 100:
            opportunities.append({"title": audit.get("title", ""), "savings_ms": round(float(savings))})
    opportunities.sort(key=lambda o: -o["savings_ms"])

    page_field = _field(data.get("loadingExperience") or {})
    scope = "page"
    if not page_field or (data.get("loadingExperience") or {}).get("origin_fallback"):
        page_field = _field(data.get("originLoadingExperience") or {})
        scope = "site" if page_field else ""

    return Speed(
        url=url, strategy=strategy,
        score=round(perf * 100) if perf is not None else None,
        lcp_ms=num("largest-contentful-paint"), cls=num("cumulative-layout-shift"),
        tbt_ms=num("total-blocking-time"),
        field_data=page_field, field_scope=scope, opportunities=opportunities[:4],
        source="pagespeed",
    )


def measure(url: str, strategy: Strategy, *, client: httpx.Client, api_key: str = "") -> Speed:
    params = {"url": url, "strategy": strategy, "category": "performance", "locale": "fr"}
    if api_key:
        params["key"] = api_key
    try:
        r = client.get(API, params=params, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        return Speed(url, strategy, error=f"PageSpeed injoignable ({type(exc).__name__})")
    if r.status_code == 429:
        return Speed(url, strategy, error="quota PageSpeed épuisé : ajouter une clé PAGESPEED_API_KEY (gratuite)")
    if r.status_code != 200:
        try:
            message = r.json().get("error", {}).get("message", "")
        except ValueError:
            message = ""
        return Speed(url, strategy, error=f"PageSpeed a refusé la mesure ({r.status_code}) {message[:120]}".strip())
    return parse(url, strategy, r.json())


# --------------------------------------------------------------------------- #
# Secours : Lighthouse lancé ici
# --------------------------------------------------------------------------- #

def _chrome() -> str:
    """Chromium : `CHROME_PATH`, sinon le navigateur installé, sinon celui de Playwright."""
    for candidate in (os.environ.get("CHROME_PATH", ""), shutil.which("chromium"),
                      shutil.which("chromium-browser"), shutil.which("google-chrome"),
                      *sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"), reverse=True)):
        if candidate and os.path.exists(candidate):
            return candidate
    return ""


def lighthouse_available() -> bool:
    return bool(shutil.which(os.environ.get("AG_LIGHTHOUSE", "lighthouse")) and _chrome())


def run_lighthouse(url: str, strategy: Strategy) -> dict:
    """Lance la CLI Lighthouse et renvoie son JSON (le `lighthouseResult` de l'API)."""
    command = [
        shutil.which(os.environ.get("AG_LIGHTHOUSE", "lighthouse")) or "lighthouse", url,
        "--quiet", "--only-categories=performance", "--locale=fr",
        "--output=json", "--output-path=stdout",
        "--chrome-flags=--headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage",
        # Sans cette en-tête, un site multilingue sert sa version anglaise.
        '--extra-headers={"Accept-Language": "fr-FR,fr;q=0.9"}',
    ]
    if strategy == "desktop":
        command.append("--preset=desktop")
    env = {**os.environ, "CHROME_PATH": _chrome()}
    done = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT, env=env, check=False)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip().splitlines()[-1] if done.stderr.strip() else "Lighthouse a échoué")
    return json.loads(done.stdout)


def measure_local(url: str, strategy: Strategy, *, runner=run_lighthouse) -> Speed:
    try:
        result = runner(url, strategy)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return Speed(url, strategy, error=f"Lighthouse : {exc}")
    if result.get("runtimeError"):
        return Speed(url, strategy, error=f"Lighthouse : {result['runtimeError'].get('message', '')}")
    speed = parse(url, strategy, {"lighthouseResult": result})
    speed.source = "lighthouse"
    return speed


def measure_all(targets: list[tuple[str, Strategy]], *, client: httpx.Client,
                api_key: str | None = None, runner=None) -> list[Speed]:
    """PageSpeed Insights d'abord, en parallèle (10 à 40 s par mesure). Ce que
    Google refuse est mesuré ici par Lighthouse, une page après l'autre : deux
    navigateurs en même temps fausseraient les temps de chargement."""
    key = os.environ.get("PAGESPEED_API_KEY", "") if api_key is None else api_key
    with ThreadPoolExecutor(max_workers=4) as pool:
        speeds = list(pool.map(lambda t: measure(t[0], t[1], client=client, api_key=key), targets))
    if runner is None and not lighthouse_available():
        return speeds
    return [measure_local(s.url, s.strategy, **({"runner": runner} if runner else {})) if s.error else s
            for s in speeds]
