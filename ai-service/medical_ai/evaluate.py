"""Real Ollama evaluation only. Writes every result, including failures, incrementally."""
import argparse
import json
import time
from pathlib import Path

from .config import Settings
from .indexer import Corpus
from .ollama import Ollama
from .rag import CorrectiveRAG


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="../evaluation/questions.json")
    parser.add_argument("--output", default="../docs/evaluation/real-results.json")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    settings = Settings()
    provider = Ollama(settings)
    health = provider.health()
    if not health["ready"]:
        raise SystemExit("Real Ollama generation and embedding models must both be available")
    corpus = Corpus("mcp_demo", settings, provider)
    started = time.monotonic()
    indexing = corpus.index_folder()
    print(json.dumps({"indexing": indexing, "seconds": time.monotonic() - started}), flush=True)
    questions = json.loads(Path(args.questions).read_text(encoding="utf-8-sig"))
    if isinstance(questions, dict):
        questions = questions.get("questions", questions.get("cases", []))
    if args.limit:
        questions = questions[:args.limit]
    rag = CorrectiveRAG(corpus, provider, settings)
    report = {"provider": "real-local-ollama", "models": health, "config": {
        "chunkSize": settings.chunk_size, "chunkOverlap": settings.chunk_overlap,
        "retrievalK": settings.retrieval_k, "minRelevantChunks": settings.min_relevant_chunks},
        "indexing": indexing, "retrievalOnly": args.retrieval_only, "results": []}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    for case in questions:
        start = time.monotonic()
        result = {"id": case["id"], "category": case.get("category"), "question": case["question"],
                  "expected": case.get("expected"), "expectedSources": case.get("expectedSources", [])}
        try:
            retrieved = corpus.retrieve(case["question"], settings.retrieval_k)
            sources = [d.metadata["source"] for d in retrieved]
            result["retrievedSources"] = sources
            result["sourceRecall"] = all(s in sources for s in case.get("expectedSources", []))
            if not args.retrieval_only:
                answer = rag.ask(case["question"])
                result.update(answer)
                expected = case.get("expected") or []
                expected = [expected] if isinstance(expected, str) else expected
                result["expectedTextPresent"] = all(str(v).casefold() in answer["answer"].casefold() for v in expected)
                cited = [s["source"] for s in answer["sources"]]
                result["expectedSourcesCited"] = all(s in cited for s in case.get("expectedSources", []))
                result["abstentionCorrect"] = answer["insufficientContext"] if case.get("allowAbstain") else not answer["insufficientContext"]
        except Exception as exc:
            result["error"] = str(exc)
        result["seconds"] = round(time.monotonic() - start, 3)
        report["results"].append(result)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k not in {"trace", "sources"}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

