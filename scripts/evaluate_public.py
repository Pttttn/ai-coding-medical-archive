"""Real local model evaluation of v1.2, including the public privacy boundary.

Run with a separate DATA_DIR; stored evidence contains checked public payloads only.
Historical evaluations remain unchanged. Expected source identity is checked locally.
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-service"))

from medical_ai.config import Settings  # noqa: E402
from medical_ai.external_output import PublicOutput  # noqa: E402
from medical_ai.indexer import Corpus  # noqa: E402
from medical_ai.ollama import Ollama  # noqa: E402
from medical_ai.rag import CorrectiveRAG  # noqa: E402
from evaluation_support import ObservedProvider, diagnostics, manifest, write_json  # noqa: E402

FORBIDDEN = ("elena testova", "ivan primerov", "testova", "primerov", "cedar clinic", "alex example", "elena.testova@example.test",
             "mc-demo-00421", "202-555-0147", "fictional cedar clinic", "elena_testova",
             '"chunkId"', '"documentId"', '"trace"', '"source"')


def assert_public(value):
    encoded = json.dumps(value, ensure_ascii=False).casefold()
    assert all(token.casefold() not in encoded for token in FORBIDDEN), "Public privacy assertion failed"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "docs/evaluation/v12-public-rag.json"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--profile", help="Reject a different environment before evaluating")
    parser.add_argument("--diagnostics", action="store_true", help="Store hashes only, never raw traces")
    args = parser.parse_args()
    settings = Settings(sample_docs_dir=ROOT / "sample_docs")
    provider = Ollama(settings)
    run_manifest = manifest(ROOT, settings, provider)
    if args.profile and run_manifest != json.loads(Path(args.profile).read_text(encoding="utf-8")):
        write_json(Path(args.output), {"completed": False, "setupError": "EVALUATION_PROFILE_MISMATCH",
                                      "manifest": run_manifest, "results": []})
        raise SystemExit("EVALUATION_PROFILE_MISMATCH")
    if args.diagnostics:
        provider = ObservedProvider(provider)
    health = provider.health()
    if not health["ready"]:
        raise SystemExit("Both local Ollama models must be ready")
    corpus = Corpus("mcp_demo", settings, provider)
    boundary = PublicOutput(corpus, provider)
    indexing = corpus.index_folder()
    rag = CorrectiveRAG(corpus, provider, settings)
    questions = json.loads((ROOT / "evaluation/questions.json").read_text(encoding="utf-8"))
    if isinstance(questions, dict):
        questions = questions["questions"]
    if args.limit:
        questions = questions[:args.limit]
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "version": "1.2",
              "provider": "real-local-ollama", "models": health,
              "codeSha256": {name: hashlib.sha256((ROOT / "ai-service/medical_ai" / name).read_bytes()).hexdigest()
                             for name in ("chunking.py", "indexer.py", "rag.py", "privacy.py", "external_output.py")},
              "config": {"chunkSize": settings.chunk_size, "chunkOverlap": settings.chunk_overlap,
                         "retrievalK": settings.retrieval_k},
              "indexing": boundary.indexing(indexing), "manifest": run_manifest, "completed": False, "results": []}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    for case in questions:
        started = time.monotonic()
        raw, checked = None, None
        if args.diagnostics:
            provider.calls.clear()
        result = {key: case[key] for key in ("id", "category", "question", "expected") if key in case}
        try:
            expected = case.get("expected") or []
            expected = [expected] if isinstance(expected, str) else expected
            raw = rag.ask(case["question"])
            result["rawExpectedTextPresent"] = all(str(v).casefold() in raw["answer"].casefold() for v in expected)
            result["rawExpectedSourcesCited"] = all(
                path in [source["source"] for source in raw["sources"]]
                for path in case.get("expectedSources", []))
            result["rawAbstentionCorrect"] = (raw["insufficientContext"] if case.get("allowAbstain")
                                               else not raw["insufficientContext"])
            checked = boundary.checked(raw["sources"], answer=raw["answer"],
                                       insufficient_context=raw["insufficientContext"],
                                       answer_parts=raw.get("answerParts"))
            assert_public(checked)
            result["privacyPassed"] = True
            result["expectedTextPresent"] = all(str(v).casefold() in checked["answer"].casefold() for v in expected)
            local_sources = [source["source"] for source in boundary.resolve_local(checked["responseRef"]).values()]
            result["expectedSourcesCited"] = all(path in local_sources for path in case.get("expectedSources", []))
            result["abstentionCorrect"] = (checked["insufficientContext"] if case.get("allowAbstain")
                                           else not checked["insufficientContext"])
            result["public"] = checked
        except Exception as exc:
            # Exception messages and raw RAG payloads must not become public evidence artifacts.
            result["privacyPassed"] = False
            result["errorType"] = type(exc).__name__
            result["errorCode"] = getattr(exc, "code", "EVALUATION_FAILED")
        if args.diagnostics:
            result["diagnostics"] = diagnostics(raw, provider.calls, checked)
        result["passed"] = all(result.get(key, False) for key in
                               ("privacyPassed", "expectedTextPresent", "expectedSourcesCited", "abstentionCorrect"))
        result["seconds"] = round(time.monotonic() - started, 3)
        report["results"].append(result)
        report["summary"] = {"passed": sum(row["passed"] for row in report["results"]),
                             "total": len(report["results"]),
                             "privacyPassed": sum(row["privacyPassed"] for row in report["results"])}
        write_json(output, report)
        print(json.dumps({key: value for key, value in result.items() if key != "public"}, ensure_ascii=False), flush=True)
    report["completed"] = True
    write_json(output, report)
    provider.client.close()
    corpus.db.close()
    print(json.dumps(report["summary"]), flush=True)


if __name__ == "__main__":
    main()
