"""Validation en un geste depuis Telegram.

Deux règles de sécurité, tenues ici et nulle part ailleurs :

1. **Seul le propriétaire décide.** N'importe qui peut trouver un bot Telegram
   et lui écrire. Une décision n'est appliquée que si elle vient de l'identifiant
   déclaré dans `TELEGRAM_OWNER_ID`. Les autres sont ignorés en silence.
2. **Le jeton ne sort jamais.** Il fait partie de l'URL de l'API ; toute erreur
   réseau est nettoyée avant d'être journalisée.

On parle à l'API HTTP directement : quatre méthodes suffisent, une bibliothèque
de plus n'apporterait rien.
"""

from __future__ import annotations

import html
import os
import sqlite3
from datetime import datetime

import httpx2 as httpx

from .. import store

API = "https://api.telegram.org"

KIND_LABEL = {
    "publication": ("🟢", "Publication"),
    "depense": ("🟠", "Dépense"),
    "contact": ("🔵", "Prospection"),
    "site": ("🟣", "Modification de site"),
}

HELP = (
    "<b>Agent Growth</b>\n\n"
    "/attente — ce qui attend ta validation\n"
    "/resultat — le résultat du portefeuille sur 30 jours\n"
    "/aide — ce message"
)


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, token: str, owner_id: int | None, *, client: httpx.Client | None = None):
        if not token:
            raise ValueError("Jeton Telegram manquant.")
        self._token = token
        self.owner_id = owner_id
        self._client = client or httpx.Client(timeout=40.0)

    # ------------------------------------------------------------------ API

    def call(self, method: str, **payload: object) -> object:
        try:
            response = self._client.post(f"{API}/bot{self._token}/{method}", json=payload)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TelegramError(self._clean(f"{method} : {type(exc).__name__} {exc}")) from None
        if not data.get("ok"):
            raise TelegramError(self._clean(f"{method} : {data.get('description', 'erreur inconnue')}"))
        return data.get("result")

    def _clean(self, text: str) -> str:
        return text.replace(self._token, "***")

    # ----------------------------------------------------------- notifications

    def notify(self, text: str) -> int | None:
        """Message au propriétaire. Sans propriétaire déclaré, on n'envoie rien."""
        if self.owner_id is None:
            return None
        result = self.call("sendMessage", chat_id=self.owner_id, text=text,
                           parse_mode="HTML", disable_web_page_preview=True)
        return int(result["message_id"])  # type: ignore[index]

    def notify_approval(self, approval: sqlite3.Row) -> int | None:
        if self.owner_id is None:
            return None
        result = self.call(
            "sendMessage",
            chat_id=self.owner_id,
            text=format_approval(approval),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup={"inline_keyboard": [[
                {"text": "✅ Valider", "callback_data": f"ok:{approval['id']}"},
                {"text": "❌ Refuser", "callback_data": f"no:{approval['id']}"},
            ]]},
        )
        return int(result["message_id"])  # type: ignore[index]

    # --------------------------------------------------------------- réception

    def poll(self, conn: sqlite3.Connection, offset: int | None, *, timeout: int = 25) -> int | None:
        """Lit les nouveaux messages et les traite. Renvoie le prochain décalage."""
        updates = self.call("getUpdates", offset=offset, timeout=timeout,
                            allowed_updates=["message", "callback_query"]) or []
        for update in updates:  # type: ignore[union-attr]
            offset = int(update["update_id"]) + 1
            try:
                self.handle(conn, update)
            except TelegramError as exc:
                store.log(conn, action="erreur Telegram", rationale=str(exc))
        return offset

    def handle(self, conn: sqlite3.Connection, update: dict) -> None:
        if "callback_query" in update:
            self._on_button(conn, update["callback_query"])
        elif "message" in update:
            self._on_message(conn, update["message"])

    def _is_owner(self, user: dict | None) -> bool:
        return self.owner_id is not None and user is not None and int(user.get("id", 0)) == self.owner_id

    def _on_button(self, conn: sqlite3.Connection, query: dict) -> None:
        if not self._is_owner(query.get("from")):
            # Pas un mot de plus : on ne confirme même pas que la demande existe.
            store.log(conn, action="décision refusée : expéditeur inconnu",
                      rationale=f"identifiant {query.get('from', {}).get('id')}")
            self.call("answerCallbackQuery", callback_query_id=query["id"])
            return

        verb, _, raw_id = str(query.get("data", "")).partition(":")
        if verb not in ("ok", "no") or not raw_id.isdigit():
            self.call("answerCallbackQuery", callback_query_id=query["id"])
            return

        approval_id = int(raw_id)
        applied = store.decide(conn, approval_id, approve=(verb == "ok"), by="telegram")
        row = store.get_approval(conn, approval_id)

        if applied:
            note = "Validé" if verb == "ok" else "Refusé"
        else:
            note = {"approuve": "Déjà validé", "refuse": "Déjà refusé",
                    "expire": "Expiré — rien n'a été appliqué"}.get(row["state"] if row else "", "Introuvable")
        self.call("answerCallbackQuery", callback_query_id=query["id"], text=note)

        message = query.get("message") or {}
        if row is not None and message.get("message_id"):
            self.call(
                "editMessageText",
                chat_id=message["chat"]["id"],
                message_id=message["message_id"],
                text=format_approval(row) + f"\n\n<b>{html.escape(note)}</b> · {_hhmm()}",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

    def _on_message(self, conn: sqlite3.Connection, message: dict) -> None:
        text = str(message.get("text", "")).strip()
        user = message.get("from")
        chat_id = message.get("chat", {}).get("id")

        if not self._is_owner(user):
            # Seul cas où l'on répond à un inconnu : la mise en route, quand aucun
            # propriétaire n'est encore déclaré, pour lui donner son identifiant.
            if self.owner_id is None and text.startswith("/start") and user:
                self.call("sendMessage", chat_id=chat_id, parse_mode="HTML",
                          text=f"Ton identifiant Telegram est <code>{int(user['id'])}</code>.\n"
                               "Déclare-le dans la variable <code>TELEGRAM_OWNER_ID</code>, "
                               "puis redémarre le service.")
            return

        command = text.split()[0].split("@")[0].lower() if text else ""
        if command in ("/start", "/aide", "/help"):
            self.notify(HELP)
        elif command == "/attente":
            self.notify(format_pending(store.pending_approvals(conn)))
        elif command == "/resultat":
            self.notify(format_digest(conn))
        else:
            self.notify("Je ne connais pas cette commande.\n\n" + HELP)


# --------------------------------------------------------------------------- #
# Mise en forme — le texte que l'humain voit avant de dire oui
# --------------------------------------------------------------------------- #

def format_approval(row: sqlite3.Row) -> str:
    dot, label = KIND_LABEL.get(row["kind"], ("⚪", row["kind"]))
    lines = [f"{dot} <b>{html.escape(row['brand_name'] or 'Portefeuille')}</b> — {label}",
             html.escape(row["summary"])]
    if row["amount_eur"] is not None:
        lines.append(f"<b>Montant engagé : {row['amount_eur']:.0f} €</b>")
    if row["detail"]:
        lines.append(f"\n<i>{html.escape(row['detail'][:700])}</i>")
    if row["expires_at"]:
        lines.append(f"\nExpire le {_fr_datetime(row['expires_at'])} (UTC)")
    return "\n".join(lines)


def format_pending(rows: list[sqlite3.Row]) -> str:
    if not rows:
        return "Rien n'attend ta validation."
    lines = [f"<b>{len(rows)} en attente</b>"]
    for row in rows[:20]:
        dot, label = KIND_LABEL.get(row["kind"], ("⚪", row["kind"]))
        lines.append(f"{dot} {html.escape(row['brand_name'] or '—')} · {html.escape(row['summary'][:90])}")
    return "\n".join(lines)


def format_digest(conn: sqlite3.Connection, *, days: int = 30) -> str:
    """Le résultat d'abord, comme dans la console (ADR-014)."""
    rows = store.portfolio(conn, days=days)
    if not rows:
        return "Aucune marque enregistrée."
    lines = [f"<b>Résultat — {days} derniers jours</b>"]
    for r in rows:
        o = r["outcome"]
        name = html.escape(r["brand"]["name"])
        if o["measured"]:
            cpa = f"{o['cpa']:.0f} €" if o["cpa"] is not None else "—"
            lines.append(f"• <b>{name}</b> : {o['acquired']:.0f} acquisitions, "
                         f"{o['cost']:.0f} € dépensés, {cpa} par acquisition")
        else:
            lines.append(f"• <b>{name}</b> : aucun résultat mesuré")
    pending = store.pending_approvals(conn)
    if pending:
        lines.append(f"\n{len(pending)} validation(s) en attente — /attente")
    return "\n".join(lines)


def _fr_datetime(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m à %H:%M")
    except ValueError:
        return iso


def _hhmm() -> str:
    return datetime.now().strftime("%H:%M")


def from_env() -> Telegram | None:
    """Le bot, si le jeton est configuré. Sans jeton, le système tourne sans
    notifications — et la console reste le moyen de valider."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return None
    owner = os.environ.get("TELEGRAM_OWNER_ID", "").strip()
    return Telegram(token, int(owner) if owner.lstrip("-").isdigit() else None)
