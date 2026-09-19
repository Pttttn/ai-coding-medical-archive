from medical_ai.rag import CorrectiveRAG


def test_graph_rewrite_grade_answer_sources(services, provider, settings):
    services.demo.index_document("d", "visit.md", 1, "SYN-CASE-7F29")
    result = services.demo_rag.ask("What code on 2025-03-12, not 2024?")
    assert result["sources"][0]["source"] == "visit.md"
    assert result["retryCount"] == 0
    assert [t["node"] for t in result["trace"]] == ["rewrite_query", "retrieve", "grade_chunks", "generate_answer"]
    assert "not 2024" in result["trace"][0]["query"]
    assert sum("grade_chunks" in call[0] for call in provider.calls) == 1


def test_graph_maximum_three_retrievals_then_abstains(services, provider):
    services.demo.index_document("d", "visit.md", 1, "unrelated")
    provider.relevant = False
    result = services.demo_rag.ask("missing fact")
    assert result["insufficientContext"] and result["sources"] == []
    assert result["retryCount"] == 2
    assert sum(t["node"] == "retrieve" for t in result["trace"]) == 3
    assert sum(t["node"] == "broaden_query" for t in result["trace"]) == 2
    assert not any("generate_answer" in call[0] for call in provider.calls)


def test_empty_graph_abstains_and_real_archive_hides_content_trace(services):
    result = services.archive_rag.ask("No documents")
    assert result["insufficientContext"]
    assert "trace" not in result


def test_configured_sufficiency_causes_retry(services, provider, settings):
    settings.min_relevant_chunks = 2
    services.demo.index_document("d", "visit.md", 1, "one relevant chunk")
    rag = CorrectiveRAG(services.demo, provider, settings)
    result = rag.ask("fact")
    assert result["retryCount"] == 2 and result["insufficientContext"]



def test_fabricated_answer_quote_is_never_returned(services, provider):
    services.demo.index_document("d", "source.md", 1, "No dizziness. Intake unknown.")
    real_json = provider.json

    def invent(task, payload, schema=None):
        if "generate_answer" in task:
            return {"evidence": [{"citation": 1, "quote": "Medication was taken."}], "insufficientContext": False}
        return real_json(task, payload, schema)

    provider.json = invent
    result = services.demo_rag.ask("Was medication taken?")
    assert result["insufficientContext"] and result["sources"] == []
    assert "Medication was taken" not in result["answer"]
