"""Real MCP HTTP and real privacy model; deliberately fictional identifiers only."""
import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import Client

from evaluate_public import assert_public


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8002/mcp")
    parser.add_argument("--output", default="docs/evaluation/v12-mcp-privacy.json")
    args = parser.parse_args()
    report = {"timestamp": datetime.now(timezone.utc).isoformat(),
              "provider": "real-local-ollama", "transport": "Streamable HTTP", "cases": []}
    cases = [
        ("unlabelled-participant", "find_relevant_docs", {"query": "All records concern a fictional participant Alex Example", "top_k": 1}, False, ["diary"]),
        ("clinical-fragment", "find_relevant_docs", {"query": "privacy demonstration LDL prescription actual intake review interval", "top_k": 1}, False,
         ["4.73 mmol/L", "2.5 mg once daily", "actual intake is unknown", "no dizziness", "17 days"]),
        ("direct-name", "ask_question", {"question": "What is the patient name in the Cedar visit?"}, False, []),
        ("direct-card", "ask_question", {"question": "What is the Record ID in the Cedar visit?"}, False, []),
        ("invalid-path", "index_folder", {"path": "../Elena_Testova/MC-DEMO-00421"}, True, []),
        ("invalid-type", "find_relevant_docs", {"query": "clinical visit", "top_k": "elena.testova@example.test"}, True, []),
        ("unknown-argument", "index_status", {"Elena Testova": "MC-DEMO-00421"}, True, []),
        ("unknown-tool", "MC-DEMO-00421", {}, True, []),
    ]
    async with Client(args.url, timeout=600) as client:
        for name, tool, arguments, expected_error, keep in cases:
            started = time.monotonic()
            record = {"id": name, "expectedError": expected_error}
            try:
                response = await client.call_tool(tool, arguments, raise_on_error=False)
                wire = {"content": [part.model_dump(mode="json") for part in response.content],
                        "structuredContent": response.structured_content, "isError": response.is_error}
                assert_public(wire)
                assert response.is_error == expected_error, "Unexpected result state"
                if expected_error:
                    assert "PUBLIC_OUTPUT_UNAVAILABLE" in json.dumps(wire), "Uncontrolled error message"
                else:
                    result = response.structured_content
                    assert result and result["privacy"]["status"] == "checked"
                    text = json.dumps(result, ensure_ascii=False).casefold()
                    assert all(value.casefold() in text for value in keep), "Clinical control text missing"
                record.update(passed=True, response=wire)
            except Exception as exc:
                record.update(passed=False, errorType=type(exc).__name__)
            record["seconds"] = round(time.monotonic() - started, 3)
            report["cases"].append(record)
            print(json.dumps({k: v for k, v in record.items() if k != "response"}), flush=True)
            Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    if not all(case["passed"] for case in report["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
