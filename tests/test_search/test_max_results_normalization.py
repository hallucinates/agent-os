from __future__ import annotations

import httpx
import pytest

from agentos.search.providers.brave import BraveSearchProvider
from agentos.search.providers.duckduckgo import DuckDuckGoProvider
from agentos.search.providers.tavily import TavilySearchProvider
from agentos.tools.builtin import web


@pytest.fixture(autouse=True)
def clean_search_runtime() -> None:
    web.reset_search_runtime()
    yield
    web.reset_search_runtime()


@pytest.mark.asyncio
async def test_brave_provider_clamps_non_positive_max_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = BraveSearchProvider(api_key="fake-key")
    captured_params = {}

    async def fake_get(self, url, *args, **kwargs):
        nonlocal captured_params
        captured_params = kwargs.get("params") or {}
        req = httpx.Request("GET", url)
        return httpx.Response(200, json={"web": {"results": []}}, request=req)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    await provider.search("python", max_results=-5)
    assert captured_params.get("count") == 1

    await provider.search("python", max_results=0)
    assert captured_params.get("count") == 1


@pytest.mark.asyncio
async def test_tavily_provider_clamps_non_positive_max_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = TavilySearchProvider(api_key="fake-key")
    captured_json = {}

    async def fake_post(self, url, *args, **kwargs):
        nonlocal captured_json
        captured_json = kwargs.get("json") or {}
        req = httpx.Request("POST", url)
        return httpx.Response(200, json={"results": []}, request=req)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await provider.search("python", max_results=-10)
    assert captured_json.get("max_results") == 1


@pytest.mark.asyncio
async def test_duckduckgo_provider_handles_non_positive_max_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = DuckDuckGoProvider(diagnostics=True)
    html_content = (
        '<html><body><div class="result">'
        '<h2 class="result__title"><a href="https://example.com">Title</a></h2>'
        '<div class="result__snippet">Snippet</div>'
        '</div></body></html>'
    )

    async def fake_post(self, url, *args, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(200, text=html_content, request=req)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    results = await provider.search("python", max_results=-5)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_run_web_search_payload_normalizes_max_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_limit = None

    class DummyProvider:
        async def search(self, query: str, max_results: int = 5):
            nonlocal captured_limit
            captured_limit = max_results
            return []

    monkeypatch.setattr(
        "agentos.search.registry.get_provider",
        lambda name, **kwargs: DummyProvider(),
    )

    await web.run_web_search_payload("test", max_results=0)
    assert captured_limit == 5

    await web.run_web_search_payload("test", max_results=-5)
    assert captured_limit == 5
