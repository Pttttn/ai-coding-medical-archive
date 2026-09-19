import asyncio
import socket
import threading
import time

from fastmcp import Client
import httpx
import pytest
import uvicorn

from medical_ai.main import create_mcp


@pytest.mark.asyncio
async def test_four_tools_over_real_streamable_http(services, settings, provider):
    (settings.sample_docs_dir / "visit.md").write_text("Follow-up in 17 days.", encoding="utf-8")
    mcp = create_mcp(services)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(mcp.http_app(path="/mcp"), host="127.0.0.1", port=port,
                                          log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert server.started
    try:
        async with Client(f"http://127.0.0.1:{port}/mcp") as client:
            tools = await client.list_tools()
            assert {t.name for t in tools} == {"index_folder", "index_status", "find_relevant_docs", "ask_question"}
            assert all("medical" in t.description for t in tools)
            before = await client.call_tool("index_status", {})
            assert before.data["files"] == 0
            assert provider.calls == []
            indexed = await client.call_tool("index_folder", {"path": "./sample_docs", "glob": "**/*"})
            assert indexed.data["files"] == 1
            assert all(c[0] == "embed" for c in provider.calls)
            found = await client.call_tool("find_relevant_docs", {"query": "Follow-up in 17 days.", "top_k": 2})
            assert found.data["chunks"][0]["reference"] == "S1"
            assert found.data["privacy"]["status"] == "checked"
            assert any("privacy_pass" in c[0] for c in provider.calls)
            answer = await client.call_tool("ask_question", {"question": "When is follow-up?"})
            assert "17 days" in answer.data["answer"]
            assert "documentId" not in answer.data["sources"][0]
            assert answer.data["sources"][0]["reference"] == "S1"
            assert services.public_output.resolve_local(answer.data["responseRef"])["S1"]["source"] == "visit.md"
            failed = await client.call_tool("index_folder", {"path": "../"}, raise_on_error=False)
            assert failed.is_error
        async with httpx.AsyncClient(trust_env=False) as http:
            assert (await http.post(f"http://127.0.0.1:{port}/internal/remove",
                                   json={"documentId": "a"})).status_code == 404
    finally:
        server.should_exit = True
        await asyncio.to_thread(thread.join, 3)

