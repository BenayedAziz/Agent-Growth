"""Le planificateur : ce qui tourne sans qu'on le lance.

Volontairement petit. Une tâche a un nom, une cadence, et une fonction qui
reçoit une connexion. Chaque exécution est journalisée dans `job_run` : c'est ce
qui empêche de lancer deux fois la même tâche, et ce qui rend les échecs
visibles au lieu de les avaler.

Une seule instance doit tourner (SQLite, une seule réplique sur Railway).
"""

from __future__ import annotations

import logging
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from .. import store
from ..sites import Change, adapter_for
from .telegram import Telegram, TelegramError, format_digest

log = logging.getLogger("agent_growth.worker")


@dataclass
class Context:
    """Ce dont les tâches ont besoin, injecté pour pouvoir les tester."""

    db_path: Path
    telegram: Telegram | None = None
    pack_dir: Path | None = None
    env: dict[str, str] | None = None
    client: object | None = None   # client HTTP injecté dans les adaptateurs (tests)

    @property
    def packs(self) -> Path:
        return self.pack_dir or (Path(self.db_path).parent / "a-appliquer")


@dataclass
class Job:
    name: str
    func: Callable[[object, Context], str]
    every: timedelta | None = None
    daily_at: time | None = None   # heure UTC
    description: str = ""

    def is_due(self, last_started: datetime | None, now: datetime) -> bool:
        """Pure : testable sans horloge réelle."""
        if self.every is not None:
            return last_started is None or now - last_started >= self.every
        if self.daily_at is not None:
            today_slot = datetime.combine(now.date(), self.daily_at, tzinfo=timezone.utc)
            if now < today_slot:
                return False
            return last_started is None or last_started < today_slot
        return False


# --------------------------------------------------------------------------- #
# Les tâches
# --------------------------------------------------------------------------- #

def notify_approvals(conn, ctx: Context) -> str:
    """Envoie sur Telegram chaque demande pas encore notifiée."""
    if ctx.telegram is None or ctx.telegram.owner_id is None:
        return "Telegram non configuré : validation par la console uniquement."
    sent = 0
    for row in store.pending_approvals(conn, unnotified_only=True):
        message_id = ctx.telegram.notify_approval(row)
        store.mark_notified(conn, row["id"], str(message_id))
        sent += 1
    return f"{sent} demande(s) notifiée(s)"


def expire_approvals(conn, ctx: Context) -> str:
    return f"{store.expire_stale(conn)} demande(s) expirée(s)"


def apply_site_changes(conn, ctx: Context) -> str:
    """Applique ce qui a été validé. Rien d'autre ne touche un site."""
    done = []
    for row in store.site_changes(conn, "approuve"):
        site = store.get_site(conn, row["site_id"])
        brand = conn.execute("SELECT slug, name FROM brand WHERE id = ?", (row["brand_id"],)).fetchone()
        adapter = adapter_for(site, brand_slug=brand["slug"], pack_dir=ctx.packs,
                              client=ctx.client, env=ctx.env)
        result = adapter.apply(Change.from_row(row))
        store.finish_site_change(conn, row["id"], state=result.state,
                                 result=f"{result.detail} {result.url}".strip())
        store.log(conn, brand_id=row["brand_id"], actor="agent",
                  action=f"site : {result.state}", rationale=result.detail,
                  payload={"change": row["id"], "adaptateur": adapter.name, "url": result.url})
        if ctx.telegram is not None:
            icon = {"applique": "✅", "manuel": "📋", "echec": "⚠️"}[result.state]
            try:
                ctx.telegram.notify(f"{icon} <b>{brand['name']}</b> — {row['title']}\n{result.detail}")
            except TelegramError:
                pass   # la modification est faite ; la notification n'est qu'un confort
        done.append(result.state)
    return f"{len(done)} modification(s) : " + ", ".join(done) if done else "rien à appliquer"


def collect(conn, ctx: Context) -> str:
    """La collecte de nuit. Les connecteurs arrivent un par un (ADR-013) ;
    tant qu'aucun n'est branché, on le dit plutôt que de faire semblant."""
    connected = [r["slug"] for r in store.list_integrations(conn) if r["state"] == "connecte"]
    collectors = {k: v for k, v in COLLECTORS.items() if k in connected}
    if not collectors:
        return "aucun collecteur branché"
    total = 0
    for slug, collector in collectors.items():
        total += collector(conn, ctx)
    return f"{total} mesure(s) collectée(s) via {', '.join(collectors)}"


def daily_digest(conn, ctx: Context) -> str:
    if ctx.telegram is None or ctx.telegram.owner_id is None:
        return "Telegram non configuré"
    ctx.telegram.notify(format_digest(conn))
    failures = store.recent_failures(conn, 5)
    if failures:
        ctx.telegram.notify("⚠️ Tâches en échec récemment :\n" + "\n".join(
            f"• {f['job']} ({f['started_at'][:16]}) : {f['detail'][:120]}" for f in failures))
    return "résumé envoyé"


#: Collecteurs par outil connecté. Vide pour l'instant : ils arrivent un par
#: un, dans l'ordre d'ADR-013.
COLLECTORS: dict[str, Callable[[object, Context], int]] = {}


JOBS: tuple[Job, ...] = (
    Job("notifier", notify_approvals, every=timedelta(minutes=1),
        description="envoie les demandes de validation sur Telegram"),
    Job("expirer", expire_approvals, every=timedelta(minutes=15),
        description="expire les demandes trop anciennes"),
    Job("appliquer-site", apply_site_changes, every=timedelta(minutes=5),
        description="applique sur les sites ce qui a été validé"),
    Job("collecter", collect, daily_at=time(3, 0),
        description="relève les chiffres de tous les canaux"),
    Job("resume", daily_digest, daily_at=time(6, 0),
        description="envoie le résultat du portefeuille chaque matin"),
)


# --------------------------------------------------------------------------- #
# Exécution
# --------------------------------------------------------------------------- #

def run_due(ctx: Context, *, now: datetime | None = None, jobs: tuple[Job, ...] = JOBS) -> list[str]:
    """Lance les tâches dues. Une tâche qui échoue n'empêche pas les autres."""
    now = now or datetime.now(timezone.utc)
    ran: list[str] = []
    conn = store.connect(ctx.db_path)
    try:
        for job in jobs:
            last = store.last_job_run(conn, job.name)
            last_started = datetime.fromisoformat(last["started_at"]) if last else None
            if not job.is_due(last_started, now):
                continue
            run_id = store.job_started(conn, job.name)
            try:
                detail = job.func(conn, ctx)
                store.job_finished(conn, run_id, ok=True, detail=detail)
            except Exception as exc:   # noqa: BLE001 — on journalise tout, on ne tombe jamais
                conn.rollback()
                store.job_finished(conn, run_id, ok=False,
                                   detail=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}")
                log.exception("tâche %s en échec", job.name)
            ran.append(job.name)
    finally:
        conn.close()
    return ran


def start(ctx: Context, stop: threading.Event, *, tick_seconds: float = 20.0) -> list[threading.Thread]:
    """Démarre le planificateur et l'écoute Telegram, chacun dans son fil."""

    def scheduler_loop() -> None:
        while not stop.is_set():
            try:
                run_due(ctx)
            except Exception:   # noqa: BLE001
                log.exception("boucle du planificateur")
            stop.wait(tick_seconds)

    def telegram_loop() -> None:
        offset: int | None = None
        while not stop.is_set():
            conn = store.connect(ctx.db_path)
            try:
                offset = ctx.telegram.poll(conn, offset, timeout=25)  # type: ignore[union-attr]
            except TelegramError as exc:
                log.warning("Telegram : %s", exc)
                stop.wait(10)
            except Exception:   # noqa: BLE001
                log.exception("écoute Telegram")
                stop.wait(10)
            finally:
                conn.close()

    threads = [threading.Thread(target=scheduler_loop, name="planificateur", daemon=True)]
    if ctx.telegram is not None:
        threads.append(threading.Thread(target=telegram_loop, name="telegram", daemon=True))
    for t in threads:
        t.start()
    return threads
