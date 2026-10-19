"""Le bot Telegram. La règle qui compte : seul le propriétaire décide."""

import json

import httpx2
import pytest

from agent_growth import store
from agent_growth.autonomy.telegram import Telegram, TelegramError, format_approval

OWNER = 111
STRANGER = 999
TOKEN = "123456:SECRET-TOKEN"


class FakeApi:
    """Enregistre les appels à l'API Telegram et répond comme elle."""

    def __init__(self, updates=None):
        self.calls: list[tuple[str, dict]] = []
        self.updates = updates or []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        payload = json.loads(request.content or b"{}")
        self.calls.append((method, payload))
        if method == "getUpdates":
            return httpx2.Response(200, json={"ok": True, "result": self.updates})
        if method == "sendMessage":
            return httpx2.Response(200, json={"ok": True, "result": {"message_id": 42}})
        return httpx2.Response(200, json={"ok": True, "result": True})

    def methods(self):
        return [m for m, _ in self.calls]


def bot(api, owner=OWNER):
    return Telegram(TOKEN, owner, client=httpx2.Client(transport=httpx2.MockTransport(api)))


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def pending(conn):
    bid = store.add_brand(conn, slug="oria", name="Oria", url="https://oria.fr")
    cur = conn.execute(
        "INSERT INTO campaign (brand_id, channel, name, hard_cap_eur, created_at) VALUES (?, 'meta_ads', 'Automne', 300, ?)",
        (bid, store.now()),
    )
    conn.commit()
    aid = store.request_approval(conn, kind="depense", subject_table="campaign",
                                 subject_id=int(cur.lastrowid), brand_id=bid,
                                 summary="Lancer « Automne »", amount_eur=300)
    return aid


def press(approval_id, verb="ok", user=OWNER):
    return {"callback_query": {"id": "cb1", "from": {"id": user}, "data": f"{verb}:{approval_id}",
                               "message": {"message_id": 42, "chat": {"id": user}}}}


def test_owner_can_approve_from_a_button(conn, pending):
    api = FakeApi()
    bot(api).handle(conn, press(pending))
    assert store.get_approval(conn, pending)["state"] == "approuve"
    assert store.get_approval(conn, pending)["decided_by"] == "telegram"
    assert "editMessageText" in api.methods()


def test_a_stranger_cannot_approve(conn, pending):
    """N'importe qui peut écrire à un bot. Personne d'autre ne décide."""
    api = FakeApi()
    bot(api).handle(conn, press(pending, user=STRANGER))
    assert store.get_approval(conn, pending)["state"] == "en_attente"
    # On ne lui confirme même pas que la demande existe.
    assert api.methods() == ["answerCallbackQuery"]
    assert "text" not in api.calls[0][1]


def test_nobody_can_approve_when_no_owner_is_configured(conn, pending):
    bot(FakeApi(), owner=None).handle(conn, press(pending, user=OWNER))
    assert store.get_approval(conn, pending)["state"] == "en_attente"


def test_double_press_is_reported_not_reapplied(conn, pending):
    api = FakeApi()
    b = bot(api)
    b.handle(conn, press(pending))
    b.handle(conn, press(pending))
    answers = [p.get("text") for m, p in api.calls if m == "answerCallbackQuery"]
    assert answers == ["Validé", "Déjà validé"]


def test_forged_callback_data_is_ignored(conn, pending):
    api = FakeApi()
    query = press(pending)
    query["callback_query"]["data"] = "ok:1 OR 1=1"
    bot(api).handle(conn, query)
    assert store.get_approval(conn, pending)["state"] == "en_attente"


def test_start_gives_the_id_only_during_setup(conn):
    api = FakeApi()
    msg = {"message": {"text": "/start", "from": {"id": 555}, "chat": {"id": 555}}}
    bot(api, owner=None).handle(conn, msg)
    assert "555" in api.calls[-1][1]["text"]

    api2 = FakeApi()
    bot(api2, owner=OWNER).handle(conn, msg)       # propriétaire déjà déclaré
    assert api2.calls == []                          # silence total


def test_owner_commands(conn, pending):
    api = FakeApi()
    b = bot(api)
    b.handle(conn, {"message": {"text": "/attente", "from": {"id": OWNER}, "chat": {"id": OWNER}}})
    assert "1 en attente" in api.calls[-1][1]["text"]
    b.handle(conn, {"message": {"text": "/resultat", "from": {"id": OWNER}, "chat": {"id": OWNER}}})
    assert "Résultat" in api.calls[-1][1]["text"]


def test_approval_message_shows_the_amount_and_buttons(conn, pending):
    api = FakeApi()
    bot(api).notify_approval(store.get_approval(conn, pending))
    method, payload = api.calls[-1]
    assert method == "sendMessage"
    assert payload["chat_id"] == OWNER
    assert "300 €" in payload["text"]
    buttons = payload["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in buttons] == [f"ok:{pending}", f"no:{pending}"]


def test_message_content_is_escaped(conn):
    """Un titre de campagne ne doit pas pouvoir injecter du HTML Telegram."""
    bid = store.add_brand(conn, slug="x", name="<b>X</b>", url="https://x.fr")
    cur = conn.execute("INSERT INTO content (brand_id, channel, created_at) VALUES (?, 'instagram', ?)",
                       (bid, store.now()))
    conn.commit()
    aid = store.request_approval(conn, kind="publication", subject_table="content",
                                 subject_id=int(cur.lastrowid), brand_id=bid,
                                 summary='<a href="http://evil">clic</a>')
    text = format_approval(store.get_approval(conn, aid))
    assert "<a href" not in text
    assert "&lt;a href" in text


def test_the_token_never_appears_in_errors(conn):
    def boom(request):
        raise httpx2.ConnectError("échec vers " + str(request.url))

    b = Telegram(TOKEN, OWNER, client=httpx2.Client(transport=httpx2.MockTransport(boom)))
    with pytest.raises(TelegramError) as info:
        b.notify("test")
    assert "SECRET-TOKEN" not in str(info.value)
    assert "***" in str(info.value)


def test_api_refusal_is_raised_cleanly():
    b = Telegram(TOKEN, OWNER, client=httpx2.Client(transport=httpx2.MockTransport(
        lambda r: httpx2.Response(200, json={"ok": False, "description": "Forbidden: bot was blocked"}))))
    with pytest.raises(TelegramError, match="blocked"):
        b.notify("test")
