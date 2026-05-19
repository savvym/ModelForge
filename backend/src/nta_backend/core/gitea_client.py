from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from nta_backend.core.config import get_settings

logger = logging.getLogger(__name__)


class GiteaError(Exception):
    """Base Gitea API error."""

    def __init__(self, status_code: int, message: str, body: Any | None = None) -> None:
        super().__init__(f"gitea {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.body = body


class GiteaClientError(GiteaError):
    """4xx errors — client-side / validation."""


class GiteaServerError(GiteaError):
    """5xx errors — Gitea is reachable but returning errors."""


class GiteaUnreachable(GiteaError):
    """Network failure talking to Gitea."""

    def __init__(self, message: str) -> None:
        super().__init__(0, message)


@dataclass(slots=True)
class GiteaAuthor:
    name: str
    email: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "email": self.email}


@dataclass(slots=True)
class UploadFile:
    path: str
    content_b64: str


def _decode_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    body = _decode_body(response)
    message = body.get("message", response.reason_phrase) if isinstance(body, dict) else str(body)
    if 400 <= response.status_code < 500:
        raise GiteaClientError(response.status_code, message, body)
    raise GiteaServerError(response.status_code, message, body)


class GiteaClient:
    """Thin async wrapper around the Gitea v1 API.

    All calls use the platform admin token. Commit-authoring endpoints accept an
    ``author`` argument to attribute the change to a specific user without
    requiring per-user Gitea credentials.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=f"{self._base_url}/api/v1",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/json",
            },
            timeout=timeout,
            transport=transport
            or httpx.AsyncHTTPTransport(retries=2),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise GiteaUnreachable(str(exc)) from exc
        _raise_for_status(response)
        return response

    # ----- health -----

    async def health(self) -> bool:
        try:
            response = await self._client.get("/version")
            return response.is_success
        except httpx.RequestError:
            return False

    # ----- orgs -----

    async def get_org(self, name: str) -> dict[str, Any] | None:
        try:
            response = await self._request("GET", f"/orgs/{name}")
        except GiteaClientError as exc:
            if exc.status_code == 404:
                return None
            raise
        return response.json()

    async def create_org(
        self,
        name: str,
        *,
        description: str | None = None,
        visibility: str = "private",
    ) -> dict[str, Any]:
        payload = {"username": name, "visibility": visibility}
        if description:
            payload["description"] = description
        try:
            response = await self._request("POST", "/orgs", json=payload)
        except GiteaClientError as exc:
            # 422 → org already exists. Re-fetch to be idempotent.
            if exc.status_code in (409, 422):
                existing = await self.get_org(name)
                if existing is not None:
                    return existing
            raise
        return response.json()

    async def delete_org(self, name: str) -> None:
        try:
            await self._request("DELETE", f"/orgs/{name}")
        except GiteaClientError as exc:
            if exc.status_code == 404:
                return
            raise

    # ----- repos -----

    async def get_repo(self, org: str, repo: str) -> dict[str, Any] | None:
        try:
            response = await self._request("GET", f"/repos/{org}/{repo}")
        except GiteaClientError as exc:
            if exc.status_code == 404:
                return None
            raise
        return response.json()

    async def create_repo(
        self,
        org: str,
        repo: str,
        *,
        description: str | None = None,
        default_branch: str = "main",
        private: bool = True,
        auto_init: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": repo,
            "private": private,
            "auto_init": auto_init,
            "default_branch": default_branch,
        }
        if description:
            payload["description"] = description
        try:
            response = await self._request("POST", f"/orgs/{org}/repos", json=payload)
        except GiteaClientError as exc:
            if exc.status_code in (409, 422):
                existing = await self.get_repo(org, repo)
                if existing is not None:
                    return existing
            raise
        return response.json()

    async def delete_repo(self, org: str, repo: str) -> None:
        try:
            await self._request("DELETE", f"/repos/{org}/{repo}")
        except GiteaClientError as exc:
            if exc.status_code == 404:
                return
            raise

    async def list_repos_in_org(
        self,
        org: str,
        *,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        response = await self._request(
            "GET",
            f"/orgs/{org}/repos",
            params={"page": page, "limit": limit},
        )
        total_header = response.headers.get("X-Total-Count")
        total = int(total_header) if total_header and total_header.isdigit() else len(response.json())
        return response.json(), total

    # ----- contents (tree & files) -----

    async def get_contents(
        self,
        org: str,
        repo: str,
        *,
        ref: str,
        path: str = "",
    ) -> Any:
        path = path.lstrip("/")
        url = f"/repos/{org}/{repo}/contents/{path}" if path else f"/repos/{org}/{repo}/contents"
        try:
            response = await self._request("GET", url, params={"ref": ref})
        except GiteaClientError as exc:
            if exc.status_code == 404:
                return None
            raise
        return response.json()

    async def get_file_raw(
        self,
        org: str,
        repo: str,
        *,
        ref: str,
        path: str,
    ) -> tuple[bytes, str]:
        path = path.lstrip("/")
        url = f"/repos/{org}/{repo}/media/{path}"
        try:
            response = await self._client.get(url, params={"ref": ref})
        except httpx.RequestError as exc:
            raise GiteaUnreachable(str(exc)) from exc
        _raise_for_status(response)
        return response.content, response.headers.get("content-type", "application/octet-stream")

    async def put_file(
        self,
        org: str,
        repo: str,
        *,
        path: str,
        content_b64: str,
        message: str,
        branch: str,
        author: GiteaAuthor,
        sha: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "content": content_b64,
            "message": message,
            "branch": branch,
            "author": author.to_dict(),
            "committer": author.to_dict(),
        }
        if sha is not None:
            payload["sha"] = sha
            method = "PUT"
        else:
            method = "POST"
        path = path.lstrip("/")
        response = await self._request(
            method,
            f"/repos/{org}/{repo}/contents/{path}",
            json=payload,
        )
        return response.json()

    async def batch_commit(
        self,
        org: str,
        repo: str,
        *,
        branch: str,
        message: str,
        files: list[UploadFile],
        author: GiteaAuthor,
    ) -> dict[str, Any]:
        """Single-commit multi-file upload via Gitea 1.20+ batch contents API."""
        if not files:
            raise ValueError("batch_commit requires at least one file")

        existing_paths: dict[str, str] = {}
        for file in files:
            try:
                entry = await self.get_contents(org, repo, ref=branch, path=file.path)
            except GiteaClientError as exc:
                if exc.status_code == 404:
                    entry = None
                else:
                    raise
            if isinstance(entry, dict) and entry.get("sha"):
                existing_paths[file.path] = entry["sha"]

        actions: list[dict[str, Any]] = []
        for file in files:
            action: dict[str, Any] = {
                "operation": "update" if file.path in existing_paths else "create",
                "path": file.path,
                "content": file.content_b64,
            }
            if file.path in existing_paths:
                action["sha"] = existing_paths[file.path]
            actions.append(action)

        payload = {
            "branch": branch,
            "message": message,
            "files": actions,
            "author": author.to_dict(),
            "committer": author.to_dict(),
        }
        response = await self._request(
            "POST",
            f"/repos/{org}/{repo}/contents",
            json=payload,
        )
        return response.json()

    # ----- commits & branches -----

    async def list_commits(
        self,
        org: str,
        repo: str,
        *,
        ref: str,
        path: str | None = None,
        page: int = 1,
        limit: int = 30,
    ) -> tuple[list[dict[str, Any]], int]:
        params: dict[str, Any] = {"sha": ref, "page": page, "limit": limit}
        if path:
            params["path"] = path
        response = await self._request(
            "GET",
            f"/repos/{org}/{repo}/commits",
            params=params,
        )
        total_header = response.headers.get("X-Total-Count")
        total = int(total_header) if total_header and total_header.isdigit() else len(response.json())
        return response.json(), total

    async def get_commit(self, org: str, repo: str, sha: str) -> dict[str, Any]:
        response = await self._request("GET", f"/repos/{org}/{repo}/commits/{sha}")
        return response.json()

    async def list_branches(self, org: str, repo: str) -> list[dict[str, Any]]:
        response = await self._request(
            "GET",
            f"/repos/{org}/{repo}/branches",
            params={"limit": 50},
        )
        return response.json()


_client_instance: GiteaClient | None = None


def get_gitea_client() -> GiteaClient:
    """Return the process-wide Gitea client. Built lazily on first call."""
    global _client_instance
    if _client_instance is None:
        settings = get_settings()
        token = settings.gitea_admin_token.get_secret_value()
        if not token:
            logger.warning(
                "GITEA_ADMIN_TOKEN is empty; run `make gitea.bootstrap` to populate it",
            )
        _client_instance = GiteaClient(
            settings.gitea_internal_url,
            token,
            timeout=settings.gitea_request_timeout_seconds,
        )
    return _client_instance


async def shutdown_gitea_client() -> None:
    global _client_instance
    if _client_instance is not None:
        await _client_instance.aclose()
        _client_instance = None


def encode_base64(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


def decode_base64(content_b64: str) -> bytes:
    return base64.b64decode(content_b64)
