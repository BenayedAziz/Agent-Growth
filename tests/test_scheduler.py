"""Le planificateur : quand les tâches tournent, et ce qu'elles font."""

from datetime import datetime, time, timedelta, timezone

import httpx2

from agent_growth import store
from agent_growth.autonomy import scheduler
from agent_growth.autonomy.telegram import Telegram

UTC = timezone.utc


def test_interval_job_is_due_after_its_interval():
    job = scheduler.Job("x", lambda c, ctx: "", every=timedelta(minutes=5))
    now = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    assert job.is_due(None, now)
    assert not job.is_due(now - timedelta(minutes=2), now)
    assert job.is_due(now - timedelta(minutes=5), now)


def test_daily_job_runs_once_per_day_after_its_hour():
    job = scheduler.Job("x", lambda c, ctx: "", daily_at=time(6, 0))
    before = datetime(2026, 10, 19, 5, 59, tzinfo=UTC)
    after = datetime(2026, 10, 19, 6, 1, tzinfo=UTC)
    assert not job.is_due(None, before)
    assert job.is_due(None, after)
    assert not job.is_due(after, after + timedelta(hours=3))           # déjà fait aujourd'hui
    assert job.is_due(after, after + timedelta(days=1))                 # demain


def test_a_failing_job_is_recorded_and_does_not_stop_the_others(tmp_path):
    db = tmp_path / "c.db"

    def broken(conn, ctx):
        raise RuntimeError("API en panne")

    jobs = (scheduler.Job("casse", broken, every=timedelta(minutes=1)),
            scheduler.Job("sain", lambda c, ctx: "ok", every=timedelta(minutes=1)))
    ran = scheduler.run_due(scheduler.Context(db_path=db), jobs=jobs)
    assert ran == ["casse", "sain"]

    conn = store.connect(db)
    assert store.last_job_run(conn, "casse")["ok"] == 0
    assert "API en panne" in store.last_job_run(conn, "casse")["detail"]
    assert store.last_job_run(conn, "sain")["ok"] == 1
    assert [f["job"] for f in store.recent_failures(conn)] == ["casse"]


def test_a_job_does_not_run_twice_in_its_interval(tmp_path):
    db = tmp_path / "c.db"
    count = []
    jobs = (scheduler.Job("x", lambda c, ctx: count.append(1) or "", every=timedelta(hours=1)),)
    ctx = scheduler.Context(db_path=db)
    scheduler.run_due(ctx, jobs=jobs)
    scheduler.run_due(ctx, jobs=jobs)
    assert len(count) == 1


def test_approved_site_change_is_applied_end_to_end(tmp_path):
    """Proposer → valider → le planificateur écrit sur WordPress → c'est journalisé."""
    db = tmp_path / "c.db"
    conn = store.connect(db)
    bid = store.add_brand(conn, slug="egy", name="Egyptours", url="https://egy.fr")
    site_id = store.add_site(conn, bid, "https://egy.fr", platform="wordpress",
                             secret_ref="WP_EGY", config={"user": "admin"})
    change_id, aid = store.propose_site_change(conn, site_id, kind="page_create",
                                               title="Croisière", body="<p>…</p>")
    store.decide(conn, aid, approve=True, by="test")
    conn.close()

    wp = httpx2.Client(transport=httpx2.MockTransport(
        lambda r: httpx2.Response(201, json={"id": 5, "status": "draft", "link": "https://egy.fr/?p=5"})))
    ctx = scheduler.Context(db_path=db, env={"WP_EGY": "pass"}, client=wp, pack_dir=tmp_path / "packs")
    scheduler.apply_site_changes(store.connect(db), ctx)

    conn = store.connect(db)
    row = conn.execute("SELECT state, result FROM site_change WHERE id = ?", (change_id,)).fetchone()
    assert row["state"] == "applique"
    assert "brouillon" in row["result"]
    assert any("site : applique" in r["action"] for r in store.recent_log(conn))


def test_speedmedia_change_becomes_a_paste_ready_pack(tmp_path):
    db = tmp_path / "c.db"
    conn = store.connect(db)
    bid = store.add_brand(conn, slug="egyptours", name="Egyptours", url="https://egyptours.fr")
    site_id = store.add_site(conn, bid, "https://egyptours.fr", platform="speedmedia")
    change_id, aid = store.propose_site_change(conn, site_id, kind="page_create",
                                               title="Le Caire en 4 jours", body="<p>…</p>")
    store.decide(conn, aid, approve=True, by="test")
    scheduler.apply_site_changes(conn, scheduler.Context(db_path=db, pack_dir=tmp_path / "packs"))
    assert store.site_changes(conn, "manuel")[0]["id"] == change_id
    assert list((tmp_path / "packs" / "egyptours").glob("*.md"))


def test_pending_approvals_are_sent_once_to_telegram(tmp_path):
    db = tmp_path / "c.db"
    conn = store.connect(db)
    bid = store.add_brand(conn, slug="o", name="Oria", url="https://oria.fr")
    cur = conn.execute("INSERT INTO content (brand_id, channel, created_at) VALUES (?, 'instagram', ?)",
                       (bid, store.now()))
    conn.commit()
    store.request_approval(conn, kind="publication", subject_table="content",
                           subject_id=int(cur.lastrowid), brand_id=bid, summary="Post")

    sent = []
    api = httpx2.Client(transport=httpx2.MockTransport(
        lambda r: sent.append(1) or httpx2.Response(200, json={"ok": True, "result": {"message_id": 9}})))
    ctx = scheduler.Context(db_path=db, telegram=Telegram("1:x", 111, client=api))
    scheduler.notify_approvals(conn, ctx)
    scheduler.notify_approvals(conn, ctx)
    assert len(sent) == 1


def test_collect_says_so_when_nothing_is_connected(tmp_path):
    conn = store.connect(tmp_path / "c.db")
    assert scheduler.collect(conn, scheduler.Context(db_path=tmp_path / "c.db")) == "aucun collecteur branché"
