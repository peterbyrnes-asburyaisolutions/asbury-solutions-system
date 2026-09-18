"""Opt-in bearer auth for ``/api/v{1,2}/memory/*``."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from everos.config import load_settings
from everos.core.middleware import MemoryApiAuthMiddleware
from everos.entrypoints.api.app import create_app

_TOKEN = "test-secret-token"


def _memory_stub_app(*, token: str | None) -> FastAPI:
    """Minimal app: one protected memory route + open /health."""
    app = FastAPI()
    if token:
        app.add_middleware(MemoryApiAuthMiddleware, token=token)

    @app.get("/api/v1/memory/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/api/v2/memory/ping")
    async def ping_v2() -> dict[str, str]:
        return {"ok": "2"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/knowledge/ping")
    async def knowledge() -> dict[str, str]:
        return {"ok": "k"}

    return app


@pytest.fixture
async def authed_client() -> AsyncIterator[AsyncClient]:
    app = _memory_stub_app(token=_TOKEN)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def open_client() -> AsyncIterator[AsyncClient]:
    app = _memory_stub_app(token=None)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def test_401_without_token_when_configured(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/memory/ping")
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


async def test_401_with_wrong_token(authed_client: AsyncClient) -> None:
    resp = await authed_client.get(
        "/api/v1/memory/ping",
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


async def test_200_with_correct_bearer(authed_client: AsyncClient) -> None:
    resp = await authed_client.get(
        "/api/v1/memory/ping",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": "1"}


async def test_v2_memory_also_requires_token(authed_client: AsyncClient) -> None:
    denied = await authed_client.get("/api/v2/memory/ping")
    assert denied.status_code == 401
    ok = await authed_client.get(
        "/api/v2/memory/ping",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert ok.status_code == 200


async def test_health_and_metrics_stay_open(authed_client: AsyncClient) -> None:
    assert (await authed_client.get("/health")).status_code == 200
    assert (await authed_client.get("/metrics")).status_code == 200


async def test_non_memory_api_stays_open(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/knowledge/ping")
    assert resp.status_code == 200


async def test_no_auth_required_when_unset(open_client: AsyncClient) -> None:
    resp = await open_client.get("/api/v1/memory/ping")
    assert resp.status_code == 200


async def test_create_app_mounts_auth_from_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """``create_app`` wires middleware when ``EVEROS_API__AUTH_TOKEN`` is set."""
    root = tmp_path_factory.mktemp("auth-root")
    monkeypatch.setenv("EVEROS_ROOT", str(root))
    monkeypatch.setenv("EVEROS_API__AUTH_TOKEN", _TOKEN)
    load_settings.cache_clear()

    app = create_app(lifespan_providers=[])
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        denied = await client.post("/api/v1/memory/add", json={})
        assert denied.status_code == 401

        # Auth passes; missing/invalid body → validation error, not 401.
        allowed = await client.post(
            "/api/v1/memory/add",
            json={},
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )
        assert allowed.status_code == 422

        health = await client.get("/health")
        assert health.status_code == 200

    load_settings.cache_clear()


async def test_create_app_without_token_leaves_memory_open(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    root = tmp_path_factory.mktemp("open-root")
    monkeypatch.setenv("EVEROS_ROOT", str(root))
    monkeypatch.delenv("EVEROS_API__AUTH_TOKEN", raising=False)
    load_settings.cache_clear()

    app = create_app(lifespan_providers=[])
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # No auth middleware → request reaches validation (422), not 401.
        resp = await client.post("/api/v1/memory/add", json={})
        assert resp.status_code == 422

    load_settings.cache_clear()
