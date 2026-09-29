"""A long public MCP call must not stall the shared event loop (review 2026-09-25, finding 11).

The slow answer is simulated with a blocking stub; this proves scheduling, not real model latency.
"""
import asyncio
import threading

import httpx
import pytest
from fastmcp import Client

from medical_ai.main import Services, create_app, create_mcp


class SlowRAG:
    def __init__(self):
        self.started, self.release = threading.Event(), threading.Event()

    def ask(self, question):
        self.started.set()
        assert self.release.wait(10)
        return {"answer": "", "sources": [], "insufficientContext": True}


async def wait_for(event):
    for _ in range(200):
        if event.is_set():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("slow call never started")


@pytest.mark.asyncio
async def test_long_ask_question_does_not_block_health_internal_or_status(services):
    slow = services.demo_rag = SlowRAG()
    internal = httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(services)), base_url="http://ai")
    async with Client(create_mcp(services)) as client, internal:
        pending = asyncio.create_task(client.call_tool("ask_question", {"question": "When is follow-up?"}))
        try:
            await wait_for(slow.started)
            health = await asyncio.wait_for(internal.get("/health"), 2)
            assert health.status_code == 200
            status = await asyncio.wait_for(client.call_tool("index_status", {}), 2)
            assert status.data["corpus"] == "mcp_demo"
            assert not pending.done()
        finally:
            slow.release.set()
        answer = await asyncio.wait_for(pending, 5)
        assert answer.data["insufficientContext"] is True


@pytest.mark.asyncio
async def test_model_bound_tools_queue_and_refuse_when_the_queue_is_full(settings, provider):
    services = Services(settings.model_copy(update={"mcp_max_concurrent": 1, "mcp_max_waiting": 1}), provider)
    slow = services.demo_rag = SlowRAG()
    async with Client(create_mcp(services)) as client:
        first = asyncio.create_task(client.call_tool("ask_question", {"question": "first"}))
        try:
            await wait_for(slow.started)
            queued = asyncio.create_task(client.call_tool("find_relevant_docs", {"query": "second"}))
            await asyncio.sleep(0.1)
            assert not queued.done()
            refused = await asyncio.wait_for(
                client.call_tool("ask_question", {"question": "third"}, raise_on_error=False), 2)
            assert refused.is_error
            # The public error stays the fixed message, never the internal code.
            assert "MCP_BUSY" not in str(refused.content)
        finally:
            slow.release.set()
        assert (await asyncio.wait_for(first, 5)).data["insufficientContext"] is True
        assert (await asyncio.wait_for(queued, 5)).data["privacy"]["status"] == "checked"
