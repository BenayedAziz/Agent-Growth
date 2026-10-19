"""Sites développés sur mesure : une pull request sur leur dépôt GitHub.

On n'écrit jamais directement sur la branche principale d'un site codé à la
main : on ouvre une branche et une pull request. La mise en ligne reste
l'affaire du déploiement du site — c'est une deuxième porte, et elle est voulue.
"""

from __future__ import annotations

import base64

import httpx2 as httpx

from .base import Applied, Change

API = "https://api.github.com"


class GitHubAdapter:
    name = "github"

    def __init__(self, repo: str, *, token: str, base: str = "main",
                 directory: str = "content/pages", extension: str = ".md",
                 client: httpx.Client | None = None):
        self.repo = repo.strip("/")
        self.base = base
        self.directory = directory.strip("/")
        self.extension = extension
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.client = client or httpx.Client(timeout=30.0)

    def _get(self, path: str, **params: str) -> httpx.Response:
        return self.client.get(f"{API}/repos/{self.repo}{path}", headers=self.headers, params=params)

    def _send(self, method: str, path: str, payload: dict) -> httpx.Response:
        return self.client.request(method, f"{API}/repos/{self.repo}{path}", headers=self.headers, json=payload)

    def apply(self, change: Change) -> Applied:
        if "/" not in self.repo:
            return Applied(False, "echec", "GitHub : dépôt attendu sous la forme propriétaire/nom.")
        try:
            return self._apply(change)
        except httpx.HTTPError as exc:
            return Applied(False, "echec", f"GitHub injoignable : {type(exc).__name__}")

    def _apply(self, change: Change) -> Applied:
        ref = self._get(f"/git/ref/heads/{self.base}")
        if ref.status_code in (401, 403, 404):
            return Applied(False, "echec", f"GitHub : accès refusé au dépôt {self.repo} ou branche {self.base} absente.")
        base_sha = ref.json()["object"]["sha"]

        branch = f"agent-growth/{change.id}-{change.slug}"[:120]
        created = self._send("POST", "/git/refs", {"ref": f"refs/heads/{branch}", "sha": base_sha})
        if created.status_code not in (201, 422):      # 422 : la branche existe déjà
            return Applied(False, "echec", f"GitHub : création de branche impossible ({created.status_code}).")

        if change.kind == "page_create":
            path = f"{self.directory}/{change.slug}{self.extension}"
            content = self._document(change)
        else:
            path = change.target.strip("/")
            content = change.marked_body()

        put: dict[str, object] = {
            "message": f"{'Ajoute' if change.kind == 'page_create' else 'Met à jour'} « {change.title} » (Agent Growth)",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        existing = self._get(f"/contents/{path}", ref=branch)
        if existing.status_code == 200:
            put["sha"] = existing.json()["sha"]
        elif change.kind == "page_update":
            return Applied(False, "echec", f"GitHub : fichier {path} introuvable.")

        written = self._send("PUT", f"/contents/{path}", put)
        if written.status_code not in (200, 201):
            return Applied(False, "echec", f"GitHub : écriture refusée ({written.status_code}).")

        pr = self._send("POST", "/pulls", {
            "title": f"[Agent Growth] {change.title}",
            "head": branch,
            "base": self.base,
            "body": "Proposé par Agent Growth, validé par un humain avant ouverture.\n\n"
                    "La mise en ligne a lieu à la fusion, selon le déploiement du site.",
        })
        if pr.status_code == 422:
            return Applied(True, "applique", f"Branche {branch} mise à jour (pull request déjà ouverte).")
        if pr.status_code != 201:
            return Applied(False, "echec", f"GitHub : ouverture de la pull request refusée ({pr.status_code}).")
        return Applied(True, "applique", "Pull request ouverte : en ligne après fusion.", url=pr.json().get("html_url", ""))

    @staticmethod
    def _document(change: Change) -> str:
        title = change.title.replace('"', "'")
        lines = ["---", f'title: "{title}"', f"slug: {change.slug}"]
        if change.meta.get("description"):
            lines.append(f'description: "{str(change.meta["description"]).replace(chr(34), chr(39))}"')
        if change.ai_generated:
            lines.append("ai_generated: true")
        lines += ["---", "", change.body, ""]
        return "\n".join(lines)
