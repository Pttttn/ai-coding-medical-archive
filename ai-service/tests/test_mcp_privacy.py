"""Actual HTTP transport, including text blocks and structured MCP serialization.

Deterministic providers exercise the security boundary; these are not real-model quality claims.
"""
import asyncio
import json
import socket
import threading
import time
from dataclasses import asdict

import httpx
import pytest
import uvicorn
from fastmcp import Client

from medical_ai.errors import ServiceError
from medical_ai.external_output import PUBLIC_ERROR, PublicOutput
from medical_ai.main import create_mcp

NAME = "Elena Testova"
CARD = "MC-DEMO-00421"
PHONE = "+12025550147"
EMAIL = "elena.testova@example.test"
FILENAME = "Elena_Testova_card-MC-DEMO-00421.txt"
SOURCE = (f"Patient: {NAME}\nDoctor: Ivan Primerov\nRecord ID: {CARD}\n"
          f"Phone: {PHONE}; email: {EMAIL}\n"
          "LDL 4.73 mmol/L. Prescribed 2.5 mg once daily; intake unknown. No dizziness. Review in 17 days.")


def serialized(result):
    # Inspect every content block, structured output and error field, not merely Client.data.
    return json.dumps(asdict(result), ensure_ascii=False, default=lambda value: value.model_dump(mode="json"))


def assert_private_absent(result):
    encoded = serialized(result)
    for forbidden in (NAME, "Ivan Primerov", CARD, PHONE, EMAIL, FILENAME, "chunkId", "documentId",
                      "position", "pageNumber", "source\"", "trace", "private-canary"):
        assert forbidden not in encoded


@pytest.fixture
async def public_http(services):
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
        await asyncio.sleep(0.03)
    assert server.started
    try:
        async with Client(f"http://127.0.0.1:{port}/mcp") as client:
            yield client, f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await asyncio.to_thread(thread.join, 3)


@pytest.fixture
async def indexed_public(public_http, settings):
    client, url = public_http
    (settings.sample_docs_dir / FILENAME).write_text(SOURCE, encoding="utf-8")
    await client.call_tool("index_folder", {"path": "./sample_docs"})
    return client, url


async def test_whole_answer_sources_and_local_mapping(indexed_public, services, provider):
    client, _ = indexed_public
    result = await client.call_tool("ask_question", {"question": "What are the patient's name and card number?"})
    assert not result.is_error
    assert_private_absent(result)
    data = result.data
    assert set(data) == {"answer", "sources", "responseRef", "insufficientContext", "privacy"}
    assert data["privacy"]["status"] == "checked"
    assert data["responseRef"].startswith("R") and len(data["responseRef"]) == 33
    assert "[S1]" in data["answer"]
    for source in data["sources"]:
        assert set(source) == {"reference", "text"}
    for clinical in ("4.73 mmol/L", "2.5 mg", "intake unknown", "No dizziness", "17 days"):
        assert clinical in data["answer"]
    local = PublicOutput(services.demo, provider).resolve_local(data["responseRef"])
    assert local["S1"]["source"] == FILENAME
    assert local["S1"]["chunkId"]
    assert any("privacy_pass" in call[0] for call in provider.calls)
    second = await client.call_tool("ask_question", {"question": "When is review?"})
    assert second.data["responseRef"] != data["responseRef"]


@pytest.mark.parametrize("quote", [NAME, "Testova", "Primerov", CARD, PHONE, EMAIL])
async def test_direct_identifier_only_answer_uses_source_context(indexed_public, provider, quote):
    original = provider.json

    def selected(task, payload, schema=None):
        if "generate_answer" in task:
            return {"evidence": [{"citation": 1, "quote": quote}], "insufficientContext": False}
        return original(task, payload, schema)

    provider.json = selected
    client, _ = indexed_public
    result = await client.call_tool("ask_question", {"question": "Return this patient's identifiers only."})
    assert not result.is_error
    assert_private_absent(result)
    assert quote not in result.data["answer"]


async def test_find_cannot_bypass_privacy_and_does_not_generate_answer(indexed_public, provider):
    client, _ = indexed_public
    provider.calls.clear()
    result = await client.call_tool("find_relevant_docs", {"query": "patient phone card laboratory LDL", "top_k": 1})
    assert_private_absent(result)
    assert set(result.data) == {"chunks", "responseRef", "privacy"}
    assert set(result.data["chunks"][0]) == {"reference", "text"}
    assert "4.73 mmol/L" in result.data["chunks"][0]["text"]
    assert "17 days" in result.data["chunks"][0]["text"]
    assert any("privacy_pass" in call[0] for call in provider.calls)
    assert all(call[0] == "embed" or call[0].startswith("TASK: privacy_pass") for call in provider.calls)


@pytest.mark.parametrize("tool,args", [
    ("find_relevant_docs", {"query": "LDL"}), ("ask_question", {"question": "What LDL?"})])
@pytest.mark.parametrize("failure", ["outage", "invalid", "injected", "wrong_category", "numeric_identifier", "unit", "negation", "uncertainty", "absent", "bracket_prefix"])
async def test_privacy_failure_never_returns_raw_fallback(indexed_public, provider, tool, args, failure):
    original = provider.json

    def broken(task, payload, schema=None):
        if "privacy_pass" not in task:
            return original(task, payload, schema)
        if failure == "outage":
            raise ServiceError("MODEL_UNAVAILABLE", f"private-canary {NAME} {CARD}", 503)
        if failure == "invalid":
            return {"identifiers": "private-canary", "warnings": []}
        if failure == "injected":
            return {"identifiers": [], "warnings": [], "answer": SOURCE}
        if failure == "wrong_category":
            return {"identifiers": [{"text": "LDL", "category": NAME}], "warnings": []}
        if failure == "absent":
            return {"identifiers": [{"text": "private-canary", "category": "PERSON"}], "warnings": []}
        if failure == "bracket_prefix":
            return {"identifiers": [{"text": "[PERSON_A]" + "\nDoctor:", "category": "PERSON"}], "warnings": []}
        span = {"unit": "mmol/L", "negation": "No", "uncertainty": "unknown"}.get(failure, "4.73 mmol/L")
        return {"identifiers": [{"text": span, "category": "IDENTIFIER"}], "warnings": []}

    provider.json = broken
    result = await indexed_public[0].call_tool(tool, args, raise_on_error=False)
    assert result.is_error
    assert_private_absent(result)
    encoded = serialized(result)
    assert PUBLIC_ERROR in encoded
    assert "4.73" not in encoded


async def test_model_warning_cannot_echo_identifiers(indexed_public, provider):
    original = provider.json
    provider.json = lambda task, payload, schema=None: (
        {"identifiers": [], "warnings": [SOURCE]} if "privacy_pass" in task else original(task, payload, schema))
    result = await indexed_public[0].call_tool("find_relevant_docs", {"query": "LDL"})
    assert_private_absent(result)
    assert result.data["privacy"]["warnings"] == ["AUTOMATED_CHECK_NOT_ANONYMITY_GUARANTEE",
                                                 "QUASI_IDENTIFIERS_REQUIRE_CAUTION"]


async def test_ambiguous_identifier_and_medical_number_collision_blocks(public_http, settings):
    client, _ = public_http
    (settings.sample_docs_dir / "collision.md").write_text("Record ID: 17\nReview in 17 days.", encoding="utf-8")
    await client.call_tool("index_folder", {})
    result = await client.call_tool("find_relevant_docs", {"query": "review"}, raise_on_error=False)
    assert result.is_error
    assert "17" not in serialized(result)


async def test_index_status_safe_counts_and_no_generation(public_http, settings, provider):
    client, url = public_http
    (settings.sample_docs_dir / FILENAME).write_text(SOURCE, encoding="utf-8")
    (settings.sample_docs_dir / "private-canary.zip").write_bytes(b"unhandled")
    (settings.sample_docs_dir / "private-canary.pdf").write_bytes(b"%PDF-invalid")
    before = await client.call_tool("index_status", {})
    assert before.data["files"] == 0
    assert provider.calls == []
    indexed = await client.call_tool("index_folder", {})
    assert_private_absent(indexed)
    assert indexed.data["errors"] == 1 and indexed.data["skipped"] == 1
    assert all(call[0] == "embed" for call in provider.calls)
    provider.calls.clear()
    status = await client.call_tool("index_status", {})
    assert_private_absent(status)
    assert set(status.data) == {"status", "corpus", "files", "chunks", "chunkSize", "chunkOverlap"}
    assert provider.calls == []
    tools = await client.list_tools()
    assert {tool.name for tool in tools} == {"ask_question", "find_relevant_docs", "index_folder", "index_status"}
    async with httpx.AsyncClient(trust_env=False) as http:
        assert (await http.post(url + "/internal/ask", json={"question": NAME})).status_code == 404
        assert (await http.get(url + "/health")).status_code == 404


@pytest.mark.parametrize("tool,args", [
    ("index_folder", {"path": "/data/uploads/private-canary"}),
    ("find_relevant_docs", {"query": {"private-canary": NAME}}),
    ("find_relevant_docs", {"query": "LDL", "top_k": NAME}),
    ("ask_question", {"question": NAME, "corpus": "private-canary"}),
    ("private-canary", {"question": NAME}),
])
async def test_invalid_request_errors_never_echo_inputs(public_http, tool, args):
    result = await public_http[0].call_tool(tool, args, raise_on_error=False)
    assert result.is_error
    assert_private_absent(result)
    assert PUBLIC_ERROR in serialized(result)

async def test_labelled_local_phone_propagates_to_unlabelled_answer(public_http, settings, provider):
    client, _ = public_http
    source = "Phone: 2025550147\nReview in 17 days. No dizziness."
    (settings.sample_docs_dir / "phone.md").write_text(source, encoding="utf-8")
    await client.call_tool("index_folder", {})
    original = provider.json
    provider.json = lambda task, payload, schema=None: (
        {"evidence": [{"citation": 1, "quote": "2025550147"}], "insufficientContext": False}
        if "generate_answer" in task else original(task, payload, schema))
    result = await client.call_tool("ask_question", {"question": "Return the phone number."})
    assert "2025550147" not in serialized(result)
    assert "17 days" in result.data["sources"][0]["text"]


async def test_citation_alias_does_not_rewrite_bracketed_clinical_number(public_http, settings):
    client, _ = public_http
    (settings.sample_docs_dir / "range.md").write_text("Clinical range [17] is copied exactly. Review in 17 days.",
                                                       encoding="utf-8")
    await client.call_tool("index_folder", {})
    result = await client.call_tool("ask_question", {"question": "What range and review interval?"})
    assert "[17]" in result.data["answer"] and "[S1]" in result.data["answer"]
@pytest.mark.parametrize("text", ["Blood pressure 120/80.", "Episode count 120."])
async def test_bare_clinical_number_collision_blocks(public_http, settings, text):
    client, _ = public_http
    (settings.sample_docs_dir / "collision.md").write_text("Record ID: 120\n" + text, encoding="utf-8")
    await client.call_tool("index_folder", {})
    result = await client.call_tool("find_relevant_docs", {"query": "clinical"}, raise_on_error=False)
    assert result.is_error
    assert "120" not in serialized(result)


async def test_clinic_propagates_from_labelled_source_to_answer(public_http, settings, provider):
    client, _ = public_http
    (settings.sample_docs_dir / "clinic.md").write_text("Clinic: Cedar Clinic\nReview in 17 days.", encoding="utf-8")
    await client.call_tool("index_folder", {})
    original = provider.json
    provider.json = lambda task, payload, schema=None: (
        {"evidence": [{"citation": 1, "quote": "Cedar Clinic"}], "insufficientContext": False}
        if "generate_answer" in task else original(task, payload, schema))
    result = await client.call_tool("ask_question", {"question": "Name of clinic?"})
    assert "Cedar Clinic" not in serialized(result)
    assert "17 days" in result.data["sources"][0]["text"]


@pytest.mark.parametrize("clinical_bracket", ["17", "1"])
async def test_structured_citations_preserve_number_at_paragraph_end(public_http, settings, clinical_bracket):
    client, _ = public_http
    text = f"Clinical score [{clinical_bracket}]\n\nReview in 17 days."
    (settings.sample_docs_dir / "paragraph.md").write_text(text, encoding="utf-8")
    await client.call_tool("index_folder", {})
    result = await client.call_tool("ask_question", {"question": "Clinical score and review?"})
    assert f"[{clinical_bracket}]\n\nReview" in result.data["answer"]
    assert "17 days. [S1]" in result.data["answer"]


@pytest.mark.parametrize("negative", ["отрицательная", "отрицательное", "отрицательны", "отрицателен",
                                      "отсутствует", "отсутствуют", "denied"])
def test_model_cannot_remove_negation_forms(provider, negative):
    from medical_ai.privacy import sanitize_fields
    provider.json = lambda *args: {"identifiers": [{"text": negative, "category": "PERSON"}], "warnings": []}
    with pytest.raises(ServiceError):
        sanitize_fields(provider, [f"Clinical observation: {negative}."], strict=True)
@pytest.mark.parametrize("measurement,unit", [("6.2 %", "%"), ("36.6 °C", "°C"), ("250 µg", "µg")])
def test_model_cannot_remove_unlisted_measurement_units(provider, measurement, unit):
    from medical_ai.privacy import sanitize_fields
    provider.json = lambda *args: {"identifiers": [{"text": unit, "category": "PERSON"}], "warnings": []}
    with pytest.raises(ServiceError):
        sanitize_fields(provider, [measurement], strict=True)

def test_contacts_are_opaque_before_short_name_replacement(provider):
    from medical_ai.privacy import sanitize_fields
    received = []

    def privacy(task, payload, schema=None):
        received.append(payload["package"])
        return {"identifiers": [], "warnings": []}

    provider.json = privacy
    result = sanitize_fields(provider, ["Elena Testova", SOURCE], strict=True)
    assert EMAIL not in result["texts"][1]
    assert "@" not in result["texts"][1]
    assert "[EMAIL]" in result["texts"][1]
    assert "[PERSON_A].[PERSON_A]" not in received[0]
    assert "[EMAIL]" in received[0]
    assert "17 days" in result["texts"][1]