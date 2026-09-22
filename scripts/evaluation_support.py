"""Safe fingerprints and statistics for synthetic evaluation; never exports raw traces."""
import hashlib
import importlib.metadata
import json
import platform
import statistics
from collections import Counter
from pathlib import Path

CRITERIA = ("expectedTextPresent", "expectedSourcesCited", "abstentionCorrect", "privacyPassed")
TASKS = ("rewrite_query", "broaden_query", "grade_chunks", "generate_answer", "extraction", "privacy_pass")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def manifest(root, settings, provider):
    def files_digest(paths):
        return fingerprint({p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(paths) if p.is_file()})

    health = provider.health()
    if not health.get("ready"):
        raise RuntimeError("EVALUATION_PROVIDER_NOT_READY")
    version = provider.client.get("/api/version").json()["version"]
    models = {m["name"]: m["digest"] for m in health["models"]}
    required = [root / "evaluation/questions.json", root / "ai-service/uv.lock"]
    required += [root / "scripts" / name for name in ("evaluate_public.py", "evaluate_stability.py", "evaluation_support.py")]
    if not all(p.is_file() for p in required):
        raise RuntimeError("EVALUATION_INPUT_MISSING")
    code = list((root / "ai-service/medical_ai").glob("*.py"))
    code += [root / "scripts" / name for name in
             ("evaluate_public.py", "evaluate_stability.py", "evaluation_support.py")]
    config_keys = ("chunk_size", "chunk_overlap", "retrieval_k", "min_relevant_chunks", "rag_max_corrective_retries", "llm_timeout", "max_file_bytes", "extraction_max_facts_per_batch")
    return {
        "ollamaVersion": version, "models": models,
        "llmModel": settings.llm_model, "embeddingModel": settings.embedding_model,
        "thinking": False if settings.llm_model.startswith("qwen3") else "provider-default",
        "generation": {task: provider.generation_options("TASK: " + task) for task in TASKS},
        "retrieval": {key: getattr(settings, key) for key in config_keys},
        "corpusSha256": files_digest((root / "sample_docs").rglob("*")),
        "questionsSha256": files_digest([root / "evaluation/questions.json"]),
        "codeSha256": files_digest(code),
        "dependenciesSha256": files_digest([root / "ai-service/uv.lock"]),
        "runtime": {"python": platform.python_version(), "system": platform.system(), "machine": platform.machine(),
                    "packages": {name: importlib.metadata.version(name) for name in
                                 ("chromadb", "rank-bm25", "langgraph", "pypdf", "httpx")}},
    }


class ObservedProvider:
    """Observe the real provider without changing requests or retaining source/model text."""
    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def json(self, task, payload, schema=None):
        record = {"task": task.split(".", 1)[0].removeprefix("TASK: "),
                  "inputSha256": fingerprint([task, payload, schema])}
        self.calls.append(record)
        try:
            result = self.provider.json(task, payload, schema)
            record["outputSha256"] = fingerprint(result)
            return result
        except Exception as exc:
            record["errorType"] = type(exc).__name__
            raise

    def embed(self, texts):
        record = {"task": "embed", "inputSha256": fingerprint(texts)}
        self.calls.append(record)
        try:
            result = self.provider.embed(texts)
            record["outputSha256"] = fingerprint(result)
            return result
        except Exception as exc:
            record["errorType"] = type(exc).__name__
            raise


def diagnostics(raw, calls, checked=None):
    stages = {}
    for row in (raw or {}).get("trace", []):
        stages.setdefault(row["node"], []).append(fingerprint(row))
    if raw is not None:
        stages["selectedSources"] = [fingerprint(raw["sources"])]
        stages["rawAnswer"] = [fingerprint([raw["answer"], raw["insufficientContext"]])]
    if checked is not None:
        # responseRef is deliberately random and is not a semantic difference.
        stages["publicAnswer"] = [fingerprint({k: v for k, v in checked.items() if k != "responseRef"})]
    return {"stages": stages, "calls": list(calls)}


def summarize(plan, reports, case_ids):
    """Every scheduled run stays in the denominator, including crashes and partial reports."""
    groups = {}
    for group in dict.fromkeys(p["group"] for p in plan):
        entries = [p for p in plan if p["group"] == group]
        rows_by_run = []
        complete = 0
        for entry in entries:
            report = reports.get(entry["id"], {})
            rows = report.get("results", [])
            ids = [r["id"] for r in rows]
            valid = ids == case_ids
            complete += int(valid and report.get("completed", False))
            # Reject duplicated/out-of-order/unknown results; partial prefix is useful evidence.
            if ids != case_ids[:len(ids)]:
                rows = []
            rows_by_run.append({r["id"]: r for r in rows})
        scores = [sum(row.get("passed") is True for row in rows.values()) for rows in rows_by_run]
        first = [sum(rows.get(case, {}).get("passed") is True for case in case_ids[:10]) for rows in rows_by_run]
        cases = []
        for case in case_ids:
            rows = [run.get(case, {}) for run in rows_by_run]
            passed = sum(r.get("passed") is True for r in rows)
            observed = sum(bool(r) for r in rows)
            signatures = [r.get("diagnostics", {}).get("stages", {}) for r in rows if r]
            stages = sorted({stage for sig in signatures for stage in sig})
            cases.append({"id": case, "passed": passed, "scheduled": len(entries), "observed": observed,
                          "passRate": passed / len(entries),
                          "status": "missing" if observed < len(entries) else
                                    "always-pass" if passed == len(entries) else
                                    "always-fail" if passed == 0 else "unstable",
                          "criteriaPassCounts": {k: sum(r.get(k) is True for r in rows) for k in CRITERIA},
                          "errorTypes": dict(Counter(r.get("errorType", "MISSING_RESULT") for r in rows
                                                      if not r or r.get("errorType"))),
                          "stageVariants": {stage: len({fingerprint(sig.get(stage)) for sig in signatures})
                                            for stage in stages}})
        groups[group] = {"scheduledRuns": len(entries), "completedRuns": complete,
                         "scores": scores, "min": min(scores), "median": statistics.median(scores), "max": max(scores),
                         "firstTenScores": first, "firstTenPassedEveryRun": len(case_ids) >= 10 and
                         complete == len(entries) and all(v == 10 for v in first),
                         "allQuestionsPassedEveryRun": complete == len(entries) and all(v == len(case_ids) for v in scores),
                         "cases": cases}
    return {"plannedRuns": len(plan), "questionsPerRun": len(case_ids), "groups": groups}
