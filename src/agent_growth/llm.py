"""Accès à Claude, centralisé.

Un seul endroit décide du modèle, de l'effort et de la gestion des refus. Les
outils décrivent ce qu'ils veulent (un prompt, un schéma) et reçoivent un objet
Pydantic validé.
"""

from __future__ import annotations

import os
from typing import TypeVar

import anthropic
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

#: Modèle par défaut. Surchargeable par la variable d'environnement AG_MODEL.
DEFAULT_MODEL = "claude-opus-5-5"

#: Si le modèle principal décline la demande, on retente une fois ici.
#: Les refus sont très improbables sur du marketing, mais un outil qui s'arrête
#: sans explication coûte plus cher qu'une ligne de code.
FALLBACK_MODEL = "claude-opus-4-8"

MAX_TOKENS = 16_000


class LlmError(RuntimeError):
    """Erreur côté modèle, formulée pour un humain non technique."""


def model_name() -> str:
    return os.environ.get("AG_MODEL") or DEFAULT_MODEL


#: Client injecté par les tests. En production, toujours None.
_OVERRIDE: object | None = None


def set_client(fake: object | None) -> None:
    """Remplace le client Claude (tests uniquement). `None` rétablit le vrai."""
    global _OVERRIDE
    _OVERRIDE = fake


def available() -> bool:
    """Vrai si une clé est configurée — l'interface s'en sert pour dire ce qui
    marchera et ce qui ne marchera pas, au lieu de laisser échouer."""
    return _OVERRIDE is not None or bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )


def client() -> anthropic.Anthropic:
    """Le SDK résout lui-même ANTHROPIC_API_KEY ; on ne lit jamais la clé nous-mêmes."""
    if _OVERRIDE is not None:
        return _OVERRIDE  # type: ignore[return-value]
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise LlmError(
            "Aucune clé API trouvée. Exporte ANTHROPIC_API_KEY "
            "(voir .env.example) puis relance la commande."
        )
    return anthropic.Anthropic()


def structured(
    *,
    system: str,
    prompt: str,
    output_model: type[T],
    effort: str = "high",
) -> tuple[T, str]:
    """Demande à Claude une réponse conforme à `output_model`.

    Renvoie l'objet validé et le nom du modèle qui a réellement répondu.
    """
    api = client()
    primary = model_name()
    last_error = ""

    for model in (primary, FALLBACK_MODEL):
        response = api.messages.parse(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            # Opus 5.5 réfléchit toujours ; l'effort est le seul curseur, et son
            # défaut (medium) est trop bas pour de l'analyse stratégique.
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            output_format=output_model,
        )

        if response.stop_reason == "refusal":
            detail = getattr(response.stop_details, "explanation", "") or ""
            last_error = f"{model} a décliné la demande. {detail}".strip()
            continue
        if response.stop_reason == "max_tokens":
            raise LlmError(
                "La réponse a été coupée : les sources fournies sont trop volumineuses. "
                "Réduis --max-pages ou le nombre de concurrents."
            )
        if response.parsed_output is None:
            raise LlmError(f"{model} n'a pas renvoyé de réponse exploitable.")

        return response.parsed_output, model

    raise LlmError(last_error or "Aucun modèle n'a pu traiter la demande.")



#: Recherche web côté serveur d'Anthropic. La variante 2026-02-09 filtre les
#: résultats dynamiquement ; elle est disponible sur les modèles Opus 5.5.
WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search"}


def research(*, system: str, prompt: str, max_searches: int = 5, effort: str = "medium") -> str:
    """Une recherche sur le web, synthétisée en texte.

    Sert à tout ce qui dépend de l'actualité — tendances du marché, sujets du
    moment, ce que font les concurrents cette semaine. Le résultat est un texte,
    pas un objet : il nourrit ensuite un appel structuré.
    """
    api = client()
    messages: list[dict] = [{"role": "user", "content": prompt}]
    for _ in range(4):   # « pause_turn » : la recherche a besoin d'un tour de plus
        response = api.messages.create(
            model=model_name(),
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            tools=[{**WEB_SEARCH, "max_uses": max_searches}],
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
        )
        if response.stop_reason == "refusal":
            raise LlmError("La recherche a été déclinée par le modèle.")
        if response.stop_reason == "pause_turn":
            messages = [messages[0], {"role": "assistant", "content": response.content}]
            continue
        text = "\n".join(b.text for b in response.content if getattr(b, "type", "") == "text")
        if not text.strip():
            raise LlmError("La recherche n'a rien rapporté d'exploitable.")
        return text
    raise LlmError("La recherche n'a pas abouti dans le temps imparti.")


def converse(*, system: str, messages: list[dict], tools: list[dict], effort: str = "medium"):
    """Un tour de conversation avec outils. Renvoie la réponse brute : c'est
    l'agent qui mène la boucle, parce qu'il doit appliquer les droits du compte
    à chaque outil appelé."""
    return client().messages.create(
        model=model_name(),
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
        tools=tools,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
    )
