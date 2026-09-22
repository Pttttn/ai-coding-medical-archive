"""Predeclared repeated real-model evaluation, isolated from application data."""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-service"))
from medical_ai.config import Settings  # noqa: E402
from medical_ai.ollama import Ollama  # noqa: E402
from evaluation_support import manifest, summarize, write_json  # noqa: E402


def build_plan(same, fresh):
    return ([{"id": f"same-{i:02d}", "group": "same-index", "index": "shared"} for i in range(1, same + 1)] +
            [{"id": f"fresh-{i:02d}", "group": "fresh-index", "index": f"fresh-{i:02d}"}
             for i in range(1, fresh + 1)])


def load_reports(output, plan):
    reports = {}
    for entry in plan:
        path = output / "runs" / (entry["id"] + ".json")
        if path.exists():
            try:
                reports[entry["id"]] = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                pass  # Corrupt/missing evidence is counted as missing, never as successful.
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; never reuse or overwrite a series")
    parser.add_argument("--same-index-runs", type=int, default=5)
    parser.add_argument("--fresh-index-runs", type=int, default=3)
    parser.add_argument("--profile", type=Path, help="Require an existing captured manifest to match exactly")
    parser.add_argument("--timeout", type=int, default=3600, help="Hard timeout per complete 21-question run")
    parser.add_argument("--execution", choices=["cpu", "gpu"], required=True, help="Verified against Ollama /api/ps")
    args = parser.parse_args()
    if not 1 <= args.same_index_runs <= 100 or not 1 <= args.fresh_index_runs <= 100 or args.timeout < 1:
        parser.error("Both groups require 1..100 runs and a positive timeout")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    plan = build_plan(args.same_index_runs, args.fresh_index_runs)
    questions = json.loads((ROOT / "evaluation/questions.json").read_text(encoding="utf-8"))
    questions = questions["questions"] if isinstance(questions, dict) else questions
    case_ids = [case["id"] for case in questions]
    if len(case_ids) != len(set(case_ids)):
        raise SystemExit("DUPLICATE_QUESTION_IDS")
    state = {"version": 1, "startedAt": datetime.now(timezone.utc).isoformat(), "completed": False,
             "plan": plan, "caseIds": case_ids, "timeoutSeconds": args.timeout,
             "requestedExecution": args.execution, "attempts": []}

    def save():
        state["summary"] = summarize(plan, load_reports(output, plan), case_ids)
        write_json(output / "series.json", state)

    save()  # Plan is durable before any model calls, including warmup.
    settings = Settings(sample_docs_dir=ROOT / "sample_docs")
    provider = Ollama(settings)
    try:
        expected = manifest(ROOT, settings, provider)
        if args.profile and expected != json.loads(args.profile.read_text(encoding="utf-8")):
            raise ValueError("PROFILE_MISMATCH")
        state["manifest"] = expected
        write_json(output / "profile.json", expected)
        # A fixed warmup is outside scoring and happens exactly once per series.
        provider.json("TASK: rewrite_query. Return the word ready in a query field.", {"synthetic": True},
                      {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})
        provider.embed(["Synthetic evaluation warmup."])
        running = provider.client.get("/api/ps").json()["models"]
        selected = [m for m in running if m["name"] in expected["models"]]
        state["execution"] = [{key: m.get(key) for key in ("name", "digest", "size", "size_vram")} for m in selected]
        if len(selected) != len(expected["models"]):
            raise ValueError("MODELS_NOT_LOADED")
        if any((m.get("size_vram", 0) > 0) != (args.execution == "gpu") for m in selected):
            raise ValueError("EXECUTION_MODE_MISMATCH")
        save()
        for entry in plan:
            started = time.monotonic()
            attempt = {"id": entry["id"], "status": "running", "startedAt": datetime.now(timezone.utc).isoformat()}
            state["attempts"].append(attempt)
            save()
            env = os.environ.copy()
            env.pop("MCP_DEMO_DIR", None)
            env["DATA_DIR"] = str(output / "indexes" / entry["index"])
            env["PYTHONHASHSEED"] = "0"
            command = [sys.executable, str(ROOT / "scripts/evaluate_public.py"), "--diagnostics",
                       "--profile", str(output / "profile.json"), "--output", str(output / "runs" / (entry["id"] + ".json"))]
            try:
                # CLI output is not an evidence/log channel; every question is written atomically to its report.
                child = subprocess.run(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       timeout=args.timeout, check=False)
                report = load_reports(output, [entry]).get(entry["id"], {})
                attempt["status"] = "completed" if child.returncode == 0 and report.get("completed") else "failed"
                attempt["exitCode"] = child.returncode
            except subprocess.TimeoutExpired:
                attempt["status"] = "timeout"
            except KeyboardInterrupt:
                attempt["status"] = "interrupted"
                save()
                raise
            attempt["seconds"] = round(time.monotonic() - started, 3)
            save()
            report = load_reports(output, [entry]).get(entry["id"], {})
            print(json.dumps({"run": entry["id"], "status": attempt["status"], "summary": report.get("summary")}), flush=True)
        state["completed"] = all(a["status"] == "completed" for a in state["attempts"])
        state["finishedAt"] = datetime.now(timezone.utc).isoformat()
        save()
        # Completion and quality are distinct: a fully completed series can fail acceptance.
        quality = all(g["firstTenPassedEveryRun"] for g in state["summary"]["groups"].values())
        print(json.dumps(state["summary"]), flush=True)
        return 0 if state["completed"] and quality else 2
    except Exception as exc:
        state["failureType"] = type(exc).__name__
        if str(exc) in {"PROFILE_MISMATCH", "MODELS_NOT_LOADED", "EXECUTION_MODE_MISMATCH",
                        "EVALUATION_PROVIDER_NOT_READY", "EVALUATION_INPUT_MISSING"}:
            state["failureCode"] = str(exc)
        save()
        print("SERIES_SETUP_OR_EXECUTION_FAILED", flush=True)
        return 1
    finally:
        provider.client.close()


if __name__ == "__main__":
    raise SystemExit(main())
