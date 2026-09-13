"""Regression tests for parameter aliases in ``sessions.create`` and ``sessions.patch``.

In accordance with Gateway RPC conventions, handlers accept both camelCase
and snake_case parameter names (e.g. ``agentId`` / ``agent_id``,
``displayName`` / ``display_name``, ``thinkingLevel`` / ``thinking_level``,
and ``projectId`` / ``project_id``), while preserving camelCase precedence
when both are supplied.
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

from agentos.gateway.config import GatewayConfig
from agentos.gateway.rpc import RpcContext, get_dispatcher
from agentos.session.manager import SessionManager
from agentos.session.storage import SessionStorage


@pytest_asyncio.fixture
async def storage():
    st = SessionStorage(":memory:")
    await st.connect()
    yield st
    await st.close()


@pytest_asyncio.fixture
async def manager(storage):
    return SessionManager(storage, inject_time_prefix=False)


@pytest.fixture
def dispatcher():
    return get_dispatcher()


def make_ctx(session_manager) -> RpcContext:
    ctx = RpcContext(conn_id="test-conn", config=GatewayConfig())
    ctx.session_manager = session_manager
    return ctx


async def _dispatch(dispatcher, ctx, method: str, params: dict[str, Any] | None):
    return await dispatcher.dispatch("r1", method, params, ctx)


@pytest.mark.asyncio
async def test_sessions_create_accepts_snake_case_agent_id(dispatcher, manager, storage):
    ctx = make_ctx(manager)
    res = await _dispatch(dispatcher, ctx, "sessions.create", {"agent_id": "researcher"})
    assert res.ok is True
    key = res.payload["key"]
    assert key.startswith("agent:researcher:")
    session = await storage.get_session(key)
    assert session is not None
    assert session.agent_id == "researcher"


@pytest.mark.asyncio
async def test_sessions_create_prefers_camelcase_agent_id_over_snake_case(
    dispatcher, manager, storage
):
    ctx = make_ctx(manager)
    res = await _dispatch(
        dispatcher,
        ctx,
        "sessions.create",
        {"agentId": "primary", "agent_id": "secondary"},
    )
    assert res.ok is True
    key = res.payload["key"]
    assert key.startswith("agent:primary:")
    session = await storage.get_session(key)
    assert session is not None
    assert session.agent_id == "primary"


@pytest.mark.asyncio
async def test_sessions_create_accepts_snake_case_display_name(dispatcher, manager, storage):
    ctx = make_ctx(manager)
    res = await _dispatch(
        dispatcher,
        ctx,
        "sessions.create",
        {"display_name": "  My Analysis \n"},
    )
    assert res.ok is True
    key = res.payload["key"]
    session = await storage.get_session(key)
    assert session is not None
    assert session.display_name == "My Analysis"


@pytest.mark.asyncio
async def test_sessions_create_accepts_name_alias(dispatcher, manager, storage):
    ctx = make_ctx(manager)
    res = await _dispatch(
        dispatcher,
        ctx,
        "sessions.create",
        {"name": "Sprint Planning"},
    )
    assert res.ok is True
    key = res.payload["key"]
    session = await storage.get_session(key)
    assert session is not None
    assert session.display_name == "Sprint Planning"


@pytest.mark.asyncio
async def test_sessions_create_prefers_camelcase_display_name(dispatcher, manager, storage):
    ctx = make_ctx(manager)
    res = await _dispatch(
        dispatcher,
        ctx,
        "sessions.create",
        {"displayName": "Primary Title", "display_name": "Secondary Title"},
    )
    assert res.ok is True
    key = res.payload["key"]
    session = await storage.get_session(key)
    assert session is not None
    assert session.display_name == "Primary Title"


@pytest.mark.asyncio
async def test_sessions_patch_accepts_snake_case_display_name(dispatcher, manager, storage):
    ctx = make_ctx(manager)
    session = await manager.create("agent:main:patch_test_1")
    res = await _dispatch(
        dispatcher,
        ctx,
        "sessions.patch",
        {"key": session.session_key, "display_name": "Updated Title"},
    )
    assert res.ok is True
    assert "display_name" in res.payload["updated"]
    updated = await storage.get_session(session.session_key)
    assert updated is not None
    assert updated.display_name == "Updated Title"


@pytest.mark.asyncio
async def test_sessions_patch_accepts_name_alias(dispatcher, manager, storage):
    ctx = make_ctx(manager)
    session = await manager.create("agent:main:patch_test_2")
    res = await _dispatch(
        dispatcher,
        ctx,
        "sessions.patch",
        {"key": session.session_key, "name": "Via Name Alias"},
    )
    assert res.ok is True
    assert "name" in res.payload["updated"]
    updated = await storage.get_session(session.session_key)
    assert updated is not None
    assert updated.display_name == "Via Name Alias"


@pytest.mark.asyncio
async def test_sessions_patch_accepts_snake_case_thinking_level(dispatcher, manager, storage):
    ctx = make_ctx(manager)
    session = await manager.create("agent:main:patch_test_3")
    res = await _dispatch(
        dispatcher,
        ctx,
        "sessions.patch",
        {"key": session.session_key, "thinking_level": "low"},
    )
    assert res.ok is True
    assert "thinking_level" in res.payload["updated"]
    updated = await storage.get_session(session.session_key)
    assert updated is not None
    assert updated.thinking_level == "low"


@pytest.mark.asyncio
async def test_sessions_patch_precedence_camelcase(dispatcher, manager, storage):
    ctx = make_ctx(manager)
    session = await manager.create("agent:main:patch_test_4")
    res = await _dispatch(
        dispatcher,
        ctx,
        "sessions.patch",
        {
            "key": session.session_key,
            "displayName": "Winner",
            "display_name": "Loser",
            "thinkingLevel": "high",
            "thinking_level": "low",
        },
    )
    assert res.ok is True
    assert "displayName" in res.payload["updated"]
    assert "thinkingLevel" in res.payload["updated"]
    assert "display_name" not in res.payload["updated"]
    assert "thinking_level" not in res.payload["updated"]
    updated = await storage.get_session(session.session_key)
    assert updated is not None
    assert updated.display_name == "Winner"
    assert updated.thinking_level == "high"


@pytest.mark.asyncio
async def test_sessions_patch_records_project_id_spelling(dispatcher, manager, storage):
    ctx = make_ctx(manager)
    proj = await manager.create_project(agent_id="main", name="Test Project")
    project_id = proj["project_id"]

    session = await manager.create("agent:main:patch_test_5")
    res = await _dispatch(
        dispatcher,
        ctx,
        "sessions.patch",
        {"key": session.session_key, "project_id": project_id},
    )
    assert res.ok is True
    assert "project_id" in res.payload["updated"]
    updated = await storage.get_session(session.session_key)
    assert updated is not None
    assert updated.project_id == project_id
