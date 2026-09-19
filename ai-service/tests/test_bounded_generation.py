"""Bounded local decoding and fail-closed strict RAG output contracts."""
import json

import httpx
import pytest

from medical_ai.errors import ServiceError
from medical_ai.ollama import Ollama
from medical_ai.rag import GRADE_SCHEMA, QUERY_SCHEMA


@pytest.mark.parametrize("task,expected", [
    ("rewrite_query", 128), ("broaden_query", 128), ("grade_chunks", 256),
    ("generate_answer", 1024), ("extraction", 2048), ("privacy_pass", 1024),
])
def test_every_operation_has_hard_num_predict_budget(settings, task, expected):
    provider = Ollama(settings)
    assert provider.generation_options("TASK: " + task)["num_predict"] == expected
    assert provider.generation_options("TASK: " + task)["num_ctx"] <= 16384


def test_chat_request_contains_budget_and_accepts_strict_json(settings):
    provider = Ollama(settings)
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"done_reason": "stop", "message": {"content": '{"query":"safe query"}'}})

    provider.client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost")
    assert provider.json("TASK: rewrite_query", {"question": "original"}, QUERY_SCHEMA) == {"query": "safe query"}
    assert captured[0]["options"]["num_predict"] == 128
    assert "tools" not in captured[0]


@pytest.mark.parametrize("envelope,code", [
    ({"done_reason": "length", "message": {"content": '{"query":"looks complete"}'}}, "MODEL_OUTPUT_LIMIT"),
    ({"done_reason": "stop", "message": {"content": '{"query":'}}, "MODEL_OUTPUT_INVALID"),
    ({"done_reason": "stop", "message": {"content": '{"query":"x","unexpected":"field"}'}}, "MODEL_OUTPUT_INVALID"),
    ({"done_reason": "stop", "message": {"content": '{"relevant":"true","evidence":"quote"}'}}, "MODEL_OUTPUT_INVALID"),
    ([], "MODEL_OUTPUT_INVALID"),
])
def test_incomplete_or_invalid_json_is_not_reported_as_provider_outage(settings, envelope, code):
    provider = Ollama(settings)
    provider.client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope)),
                                   base_url="http://localhost")
    schema = GRADE_SCHEMA if "relevant" in str(envelope) else QUERY_SCHEMA
    with pytest.raises(ServiceError) as error:
        provider.json("TASK: rewrite_query", {}, schema)
    assert error.value.code == code and error.value.status == 502


def test_http_failure_remains_explicit_provider_outage(settings):
    provider = Ollama(settings)
    provider.client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503)),
                                   base_url="http://localhost")
    with pytest.raises(ServiceError) as error:
        provider.json("TASK: rewrite_query", {}, QUERY_SCHEMA)
    assert error.value.code == "MODEL_UNAVAILABLE" and error.value.status == 503


@pytest.mark.parametrize("code", ["MODEL_OUTPUT_LIMIT", "MODEL_OUTPUT_INVALID"])
def test_bad_grading_is_rejected_and_reaches_bounded_abstention(services, provider, code):
    services.demo.index_document("unrelated", "other.md", 1, "No Copper Finch record here.")
    original = provider.json

    def bounded_failure(task, payload, schema=None):
        if "grade_chunks" in task:
            raise ServiceError(code, "synthetic truncated classifier output", 502)
        return original(task, payload, schema)

    provider.json = bounded_failure
    result = services.demo_rag.ask("What is the Copper Finch visit code?")
    assert result["insufficientContext"] and result["sources"] == []
    assert result["retryCount"] == 2
    assert sum(t["node"] == "retrieve" for t in result["trace"]) == 3
    errors = [grade["errorCode"] for event in result["trace"] if event["node"] == "grade_chunks"
              for grade in event["grades"]]
    assert errors == [code] * 3


def test_invalid_answer_structure_abstains_instead_of_crashing(services, provider):
    services.demo.index_document("a", "a.md", 1, "SYN-CASE-7F29")
    original = provider.json

    def invalid_answer(task, payload, schema=None):
        if "generate_answer" in task:
            return {"evidence": [42], "insufficientContext": False}
        return original(task, payload, schema)

    provider.json = invalid_answer
    result = services.demo_rag.ask("What code?")
    assert result["insufficientContext"] and result["sources"] == []


def test_unavailable_model_does_not_masquerade_as_no_archive_evidence(services, provider):
    def unavailable(*args, **kwargs):
        raise ServiceError("MODEL_UNAVAILABLE", "offline", 503)
    provider.json = unavailable
    with pytest.raises(ServiceError) as error:
        services.demo_rag.ask("What code?")
    assert error.value.code == "MODEL_UNAVAILABLE"

