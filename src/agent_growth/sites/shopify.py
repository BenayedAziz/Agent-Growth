"""Shopify, par l'API Admin GraphQL.

Le jeton se crée dans Shopify (Paramètres → Applications → Développer des
applications), avec les droits `read_content` et `write_content`. La version
d'API est réglable par site : Shopify en publie une par trimestre et les
retire au bout d'un an.
"""

from __future__ import annotations

import httpx2 as httpx

from .base import Applied, Change

CREATE = """
mutation pageCreate($page: PageCreateInput!) {
  pageCreate(page: $page) { page { id handle } userErrors { field message } }
}"""

UPDATE = """
mutation pageUpdate($id: ID!, $page: PageUpdateInput!) {
  pageUpdate(id: $id, page: $page) { page { id handle } userErrors { field message } }
}"""


class ShopifyAdapter:
    name = "shopify"

    def __init__(self, shop: str, *, token: str, api_version: str = "2026-07",
                 publish: bool = False, client: httpx.Client | None = None):
        self.shop = shop.replace("https://", "").rstrip("/")
        self.endpoint = f"https://{self.shop}/admin/api/{api_version}/graphql.json"
        self.headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
        self.publish = publish
        self.client = client or httpx.Client(timeout=30.0)

    def apply(self, change: Change) -> Applied:
        if not self.shop:
            return Applied(False, "echec", "Shopify : nom de boutique manquant dans la configuration du site.")
        page = {"title": change.title, "body": change.marked_body()}
        if change.kind == "page_create":
            page.update(handle=change.slug, isPublished=self.publish)
            query, variables, key = CREATE, {"page": page}, "pageCreate"
        else:
            target = change.target if change.target.startswith("gid://") else f"gid://shopify/Page/{change.target}"
            query, variables, key = UPDATE, {"id": target, "page": page}, "pageUpdate"

        try:
            response = self.client.post(self.endpoint, json={"query": query, "variables": variables},
                                        headers=self.headers)
        except httpx.HTTPError as exc:
            return Applied(False, "echec", f"Shopify injoignable : {type(exc).__name__}")
        if response.status_code in (401, 403):
            return Applied(False, "echec", "Shopify refuse l'accès : vérifie le jeton et ses droits write_content.")
        if response.status_code >= 400:
            return Applied(False, "echec", f"Shopify a répondu {response.status_code}.")

        data = response.json()
        if data.get("errors"):
            return Applied(False, "echec", f"Shopify : {data['errors'][0].get('message', 'erreur')}")
        result = (data.get("data") or {}).get(key) or {}
        if result.get("userErrors"):
            return Applied(False, "echec", "Shopify : " + "; ".join(e["message"] for e in result["userErrors"]))
        handle = (result.get("page") or {}).get("handle", change.slug)
        visibility = "publiée" if self.publish else "créée, non publiée"
        return Applied(True, "applique", f"Page {visibility} ({handle}).",
                       url=f"https://{self.shop}/pages/{handle}")
