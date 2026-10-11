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


def client() -> anthropic.Anthropic:
    """Le SDK résout lui-même ANTHROPIC_API_KEY ; on ne lit jamais la clé nous-mêmes."""
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
