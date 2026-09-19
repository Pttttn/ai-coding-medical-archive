"""Real Streamable HTTP MCP client checks; all sources are synthetic."""
import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import Client


def unpack(result):
    if result.structured_content is not None:
        return result.structured_content
    for content in result.content:
        if getattr(content, "text", None):
            return json.loads(content.text)
    raise AssertionError("MCP result has no readable content")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8002/mcp")
    parser.add_argument("--expect-empty", action="store_true")
    parser.add_argument("--output", default="docs/evaluation/mcp-http-smoke.json")
    args = parser.parse_args()
    events = []
    async with Client(args.url, timeout=600) as client:
        descriptions = await client.list_tools()
        assert {t.name for t in descriptions} == {"index_folder", "index_status", "find_relevant_docs", "ask_question"}
        assert all(len(t.description or "") > 80 for t in descriptions)
        for tool, arguments in [
            ("index_status", {}),
            ("index_folder", {"path": "./sample_docs", "glob": "**/*"}),
            ("index_status", {}),
            ("find_relevant_docs", {"query": "Cedar reference code", "top_k": 5}),
            ("ask_question", {"question": "What is the reference code of the Cedar visit?"}),
        ]:
            start = time.monotonic()
            value = unpack(await client.call_tool(tool, arguments))
            if not events and args.expect_empty:
                assert value["files"] == value["chunks"] == 0 and value["lastIndexedAt"] is None
            if tool == "index_folder":
                assert value["files"] >= 45 and not value["errors"], value
            if tool == "ask_question":
                assert "SYN-CASE-7F29" in value["answer"] and any(s["source"] == "visits/visit-01.md" for s in value["sources"]), value
            events.append({"tool": tool, "arguments": arguments, "seconds": round(time.monotonic() - start, 2), "result": value})
            print(f"PASS {tool}", flush=True)
        unchanged = unpack(await client.call_tool("index_folder", {"path": "./sample_docs", "glob": "**/*"}))
        assert unchanged["indexed"] == 0 and unchanged["unchanged"] >= 45
        traversal = await client.call_tool("index_folder", {"path": "../seed"}, raise_on_error=False)
        assert traversal.is_error
        events.append({"tool": "index_folder", "reindexUnchanged": unchanged["unchanged"], "pathTraversalRejected": traversal.is_error})
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "transport": "Streamable HTTP", "url": args.url, "events": events}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
