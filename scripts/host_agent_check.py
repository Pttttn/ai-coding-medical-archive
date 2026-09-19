"""Minimal LOCAL Ollama host agent selecting tools from actual MCP metadata.

This records genuine tool selection without suggesting a tool in the user question.
It is a reproducible reference host, not a claim that VSCode Copilot was tested.
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastmcp import Client


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp", default="http://127.0.0.1:8002/mcp")
    parser.add_argument("--ollama", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--output", default="docs/evaluation/v12-host-agent.json")
    args = parser.parse_args()
    question = "How many days until the follow-up recommended in the Cedar visit?"
    messages = [{"role": "system", "content": "Answer questions using available sources when needed. Do not invent facts."}, {"role": "user", "content": question}]
    events = []
    async with Client(args.mcp, timeout=600) as mcp, httpx.AsyncClient(timeout=600, trust_env=False) as http:
        tags = await http.get(args.ollama + "/api/tags")
        tags.raise_for_status()
        model_digest = next((model.get("digest") for model in tags.json().get("models", [])
                             if model.get("name") in {args.model, args.model + ":latest"}), None)
        metadata = await mcp.list_tools()
        tools = [{"type": "function", "function": {"name": tool.name, "description": tool.description, "parameters": tool.inputSchema}} for tool in metadata]
        for _ in range(6):
            response = await http.post(args.ollama + "/api/chat", json={"model": args.model, "stream": False, "think": False, "options": {"temperature": 0}, "messages": messages, "tools": tools})
            response.raise_for_status()
            message = response.json()["message"]
            messages.append(message)
            events.append({"assistant": message})
            calls = message.get("tool_calls", [])
            if not calls:
                break
            for call in calls:
                function = call["function"]
                result = await mcp.call_tool(function["name"], function["arguments"], raise_on_error=False)
                content = "\n".join(getattr(part, "text", "") for part in result.content)
                structured = result.structured_content or {}
                evidence_checked = (structured.get("privacy", {}).get("status") == "checked"
                                    and bool(structured.get("sources") or structured.get("chunks")))
                events.append({"tool": function["name"], "arguments": function["arguments"],
                               "evidenceChecked": evidence_checked, "result": content})
                messages.append({"role": "tool", "tool_name": function["name"], "content": content})
    selected = [e["tool"] for e in events if "tool" in e]
    success = any(event.get("evidenceChecked") for event in events) and "17" in messages[-1].get("content", "")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "host": "minimal local Ollama reference host", "model": args.model, "modelDigest": model_digest, "question": question, "selectedTools": selected, "success": success, "events": events}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"selectedTools": selected, "success": success}))
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
