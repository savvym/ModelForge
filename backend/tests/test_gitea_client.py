from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from nta_backend.core.gitea_client import (
    GiteaAuthor,
    GiteaClient,
    GiteaClientError,
    GiteaServerError,
    GiteaUnreachable,
    UploadFile,
)


def _json(status: int, body: Any, *, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", **(headers or {})},
    )


def _make_client(handler) -> GiteaClient:
    transport = httpx.MockTransport(handler)
    return GiteaClient("http://gitea.test", "tok-abc", timeout=1.0, transport=transport)


async def test_authorization_header_is_set():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        return _json(200, {"version": "1.22"})

    client = _make_client(handler)
    assert await client.health() is True
    assert seen["auth"] == "token tok-abc"
    await client.aclose()


async def test_create_org_is_idempotent_on_422():
    state: dict[str, int] = {"posts": 0, "gets": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v1/orgs":
            state["posts"] += 1
            return _json(422, {"message": "org already exists"})
        if request.method == "GET" and request.url.path == "/api/v1/orgs/proj-foo":
            state["gets"] += 1
            return _json(200, {"username": "proj-foo", "id": 7})
        return _json(500, {"message": "unexpected"})

    client = _make_client(handler)
    org = await client.create_org("proj-foo")
    assert org["username"] == "proj-foo"
    assert state == {"posts": 1, "gets": 1}
    await client.aclose()


async def test_delete_org_404_is_swallowed():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json(404, {"message": "not found"})

    client = _make_client(handler)
    await client.delete_org("proj-missing")  # no raise
    await client.aclose()


async def test_4xx_raises_client_error_and_5xx_raises_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/repos/o/bad":
            return _json(400, {"message": "bad input"})
        return _json(503, {"message": "down"})

    client = _make_client(handler)
    with pytest.raises(GiteaClientError) as ctx400:
        await client.get_repo("o", "bad")
    assert ctx400.value.status_code == 400
    assert "bad input" in str(ctx400.value)

    with pytest.raises(GiteaServerError) as ctx5xx:
        await client.list_branches("o", "any")
    assert ctx5xx.value.status_code == 503
    await client.aclose()


async def test_network_error_raises_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _make_client(handler)
    with pytest.raises(GiteaUnreachable):
        await client.get_org("anything")
    await client.aclose()


async def test_list_commits_uses_x_total_count():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json(
            200,
            [{"sha": "abc", "commit": {"message": "init"}, "parents": []}],
            headers={"X-Total-Count": "42"},
        )

    client = _make_client(handler)
    commits, total = await client.list_commits("o", "r", ref="main", page=1, limit=10)
    assert len(commits) == 1
    assert total == 42
    await client.aclose()


async def test_batch_commit_sends_create_or_update_actions():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.startswith("/api/v1/repos/o/r/contents/"):
            asset = path.rsplit("/", 1)[-1]
            if asset == "exists.md":
                return _json(200, {"sha": "old-sha", "path": "exists.md"})
            return _json(404, {"message": "not found"})
        if request.method == "POST" and path == "/api/v1/repos/o/r/contents":
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return _json(201, {"commit": {"sha": "new-sha"}})
        return _json(500, {"message": "x"})

    client = _make_client(handler)
    result = await client.batch_commit(
        "o",
        "r",
        branch="main",
        message="msg",
        files=[
            UploadFile(path="exists.md", content_b64="QQ=="),
            UploadFile(path="new.md", content_b64="Qg=="),
        ],
        author=GiteaAuthor(name="A", email="a@b"),
    )
    assert result["commit"]["sha"] == "new-sha"
    body = captured["body"]
    actions = {a["path"]: a for a in body["files"]}
    assert actions["exists.md"]["operation"] == "update"
    assert actions["exists.md"]["sha"] == "old-sha"
    assert actions["new.md"]["operation"] == "create"
    assert "sha" not in actions["new.md"]
    assert body["author"] == {"name": "A", "email": "a@b"}
    await client.aclose()


async def test_get_contents_returns_none_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json(404, {"message": "not found"})

    client = _make_client(handler)
    result = await client.get_contents("o", "r", ref="main", path="missing")
    assert result is None
    await client.aclose()


async def test_put_file_uses_post_when_no_sha_and_put_when_sha():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return _json(200, {"commit": {"sha": "x"}})

    client = _make_client(handler)
    author = GiteaAuthor(name="a", email="a@b")
    await client.put_file("o", "r", path="a.md", content_b64="QQ==", message="m", branch="main", author=author)
    await client.put_file(
        "o", "r", path="a.md", content_b64="QQ==", message="m", branch="main", author=author, sha="old"
    )
    assert seen == ["POST", "PUT"]
    await client.aclose()
