"""Per-``app_id`` memorize.mode override via ``mode_by_app``."""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from everos.config import Settings
from everos.config.settings import MemorizeSettings

mm = importlib.import_module("everos.service.memorize")


def test_resolve_mode_falls_back_to_global() -> None:
    cfg = MemorizeSettings(mode="chat", mode_by_app={"genesis-mini": "agent"})
    assert cfg.resolve_mode("other-app") == "chat"
    assert cfg.resolve_mode("default") == "chat"


def test_resolve_mode_uses_per_app_override() -> None:
    cfg = MemorizeSettings(mode="chat", mode_by_app={"genesis-mini": "agent"})
    assert cfg.resolve_mode("genesis-mini") == "agent"


def test_mode_by_app_empty_matches_global_mode() -> None:
    cfg = MemorizeSettings(mode="agent")
    assert cfg.mode_by_app == {}
    assert cfg.resolve_mode("genesis-mini") == "agent"


@pytest.fixture
def _patch_locked(monkeypatch: pytest.MonkeyPatch) -> Iterator[AsyncMock]:
    locked = AsyncMock(
        return_value=mm.MemorizeResult(message_count=0, status="extracted")
    )

    @asynccontextmanager
    async def _fake_lock(session_id: str) -> AsyncIterator[None]:
        yield

    monkeypatch.setattr(mm, "_memorize_locked", locked)
    monkeypatch.setattr(mm, "get_session_lock", _fake_lock)
    yield locked


async def test_memorize_passes_per_app_mode(
    monkeypatch: pytest.MonkeyPatch, _patch_locked: AsyncMock
) -> None:
    settings = Settings(
        memorize=MemorizeSettings(
            mode="chat",
            mode_by_app={"genesis-mini": "agent"},
        )
    )
    monkeypatch.setattr(mm, "load_settings", lambda: settings)

    await mm.memorize(
        {"session_id": "s1", "app_id": "genesis-mini", "messages": []},
    )
    assert _patch_locked.await_args.kwargs["mode"] == "agent"


async def test_memorize_uses_global_mode_when_app_unlisted(
    monkeypatch: pytest.MonkeyPatch, _patch_locked: AsyncMock
) -> None:
    settings = Settings(
        memorize=MemorizeSettings(
            mode="chat",
            mode_by_app={"genesis-mini": "agent"},
        )
    )
    monkeypatch.setattr(mm, "load_settings", lambda: settings)

    await mm.memorize({"session_id": "s1", "app_id": "web", "messages": []})
    assert _patch_locked.await_args.kwargs["mode"] == "chat"


async def test_memorize_default_app_id_uses_global_mode(
    monkeypatch: pytest.MonkeyPatch, _patch_locked: AsyncMock
) -> None:
    settings = Settings(
        memorize=MemorizeSettings(
            mode="agent",
            mode_by_app={"genesis-mini": "chat"},
        )
    )
    monkeypatch.setattr(mm, "load_settings", lambda: settings)

    await mm.memorize({"session_id": "s1", "messages": []})
    assert _patch_locked.await_args.kwargs["mode"] == "agent"
