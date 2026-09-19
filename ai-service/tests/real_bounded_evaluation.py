"""Targeted real regression: bounded RAG after removal, unrelated query and one-page PDF."""
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from medical_ai.config import Settings
from medical_ai.extraction import extract
from medical_ai.indexer import Corpus
from medical_ai.ollama import Ollama
from medical_ai.parsing import parse_file
from medical_ai.rag import CorrectiveRAG


def main():
    settings = Settings()
    provider = Ollama(settings)
    original = provider.client.post
    calls = []

    def capture(*args, **kwargs):
        started = time.monotonic()
        response = original(*args, **kwargs)
        if args and args[0] == "/api/chat":
            request = kwargs["json"]
            envelope = response.json()
            calls.append({"stage": request["messages"][0]["content"].split(".")[0],
                          "numPredict": request["options"]["num_predict"],
                          "numCtx": request["options"]["num_ctx"],
                          "doneReason": envelope.get("done_reason"),
                          "evalCount": envelope.get("eval_count"),
                          "seconds": round(time.monotonic() - started, 3)})
        return response

    provider.client.post = capture
    report = {"models": provider.health(), "cases": []}
    with TemporaryDirectory(prefix="bounded-rag-", ignore_cleanup_errors=True) as temporary:
        local = Settings(data_dir=Path(temporary), sample_docs_dir=Path("../sample_docs").resolve(),
                         ollama_base_url=settings.ollama_base_url)
        corpus = Corpus("mcp_demo", local, provider)
        for number in (1, 2, 3, 7, 12):
            name = f"visits/visit-{number:02d}.md"
            source = Path("../sample_docs") / name
            corpus.index_document(name, name, 1, source.read_text(encoding="utf-8"))
        corpus.index_document("copper", "copper.md", 1,
                              "The Copper Finch visit code is SYN-COPPER-931. Walking duration: 23 minutes.")
        rag = CorrectiveRAG(corpus, provider, local)
        for name, question in [("before-removal", "What is the Copper Finch visit code?"),
                               ("after-removal", "What is the Copper Finch visit code?"),
                               ("unrelated", "What is the capital of Argentina?")]:
            if name == "after-removal":
                corpus.remove("copper")
            started, offset = time.monotonic(), len(calls)
            case = {"id": name, "question": question}
            try:
                case["result"] = rag.ask(question)
            except Exception as exc:
                case["error"] = str(exc)
            case["seconds"] = round(time.monotonic() - started, 3)
            case["calls"] = calls[offset:]
            report["cases"].append(case)
    started, offset = time.monotonic(), len(calls)
    text, pages, warnings = parse_file(Path("../seed/originals/lab-01.pdf"), settings.max_file_bytes)
    case = {"id": "one-page-pdf", "text": text, "pages": [p.model_dump() for p in pages],
            "parserWarnings": warnings}
    try:
        result, extraction_warnings = extract(provider, "SYNTHETIC PDF acceptance text", pages)
        case["result"] = result.model_dump(mode="json")
        case["warnings"] = extraction_warnings
        case["nonEmptyFacts"] = bool(result.facts)
        case["allFactsPage1"] = all(f.provenance.page == 1 for f in result.facts)
    except Exception as exc:
        case["error"] = str(exc)
    case["calls"] = calls[offset:]
    case["seconds"] = round(time.monotonic() - started, 3)
    report["cases"].append(case)
    Path("../docs/evaluation/bounded-inference.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

