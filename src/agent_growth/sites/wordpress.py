"""WordPress, par l'API REST et un mot de passe d'application.

Le mot de passe d'application se crée dans l'administration WordPress
(Utilisateurs → Profil → Mots de passe d'application). Il ne donne pas accès au
compte, il se révoque d'un clic.
"""

from __future__ import annotations

import httpx2 as httpx

from .base import Applied, Change


class WordPressAdapter:
    name = "wordpress"

    def __init__(self, site_url: str, *, user: str, app_password: str,
                 status: str = "draft", client: httpx.Client | None = None):
        self.base = site_url.rstrip("/") + "/wp-json/wp/v2"
        self.auth = (user, app_password)
        # « draft » par défaut : la page existe, mais ne s'affiche pas tant qu'on
        # ne l'a pas regardée en place. Passer à « publish » dans la config du
        # site une fois la confiance établie.
        self.status = status if status in ("draft", "publish") else "draft"
        self.client = client or httpx.Client(timeout=30.0)

    def apply(self, change: Change) -> Applied:
        payload: dict[str, object] = {"title": change.title, "content": change.marked_body()}
        if change.kind == "page_create":
            payload.update(status=self.status, slug=change.slug)
            endpoint = f"{self.base}/pages"
        else:
            if not change.target.isdigit():
                return Applied(False, "echec", "Modification WordPress : identifiant de page attendu.")
            endpoint = f"{self.base}/pages/{change.target}"

        try:
            response = self.client.post(endpoint, json=payload, auth=self.auth)
        except httpx.HTTPError as exc:
            return Applied(False, "echec", f"WordPress injoignable : {type(exc).__name__}")

        if response.status_code in (401, 403):
            return Applied(False, "echec", "WordPress refuse l'accès : vérifie l'utilisateur et le mot de passe d'application.")
        if response.status_code >= 400:
            return Applied(False, "echec", f"WordPress a répondu {response.status_code} : {response.text[:200]}")

        data = response.json()
        state = "publiée" if data.get("status") == "publish" else "créée en brouillon"
        return Applied(True, "applique", f"Page {state} (n° {data.get('id')}).", url=data.get("link", ""))
