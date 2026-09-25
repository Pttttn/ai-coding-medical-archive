# Standalone CLI resolves the repository import path before importing services.
# ruff: noqa: E402
"""Synthetic-only VISIT extractor comparison over SSH. Not Docker/backend/index/QA acceptance.

Only frozen fixture originals reach the model; the key stays on the remote host.
Uses the already established Ollama-to-llama.cpp SSH transport and the same VISIT prompt.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-service"))
import httpx
import evaluate_clinical_ssh as remote
from evaluate_visit_ingestion import key, score, summarize
from visit_semantic_metrics import evaluate_semantics, summarize_semantics
from medical_ai.config import Settings
from medical_ai.ollama import Ollama
from medical_ai.schemas import Page
from medical_ai.source_ir import SourceIR, build_source_ir
from medical_ai.visit import VISIT_PROMPT_VERSION, annotate_visit, project_visit
from medical_ai.visit_review import (
    REVIEW_PROMPT_VERSION,
    annotate_reviewed_visit,
    project_reviewed_visit,
)


def run(args):
    if args.output.exists():
        raise SystemExit("Refusing to overwrite a previous attempt.")
    if args.ssh_target.startswith("-") or not 1 <= args.ssh_port <= 65535:
        raise SystemExit("Invalid SSH target/port.")
    remote.MODEL, remote.KEY_FILE, remote.REMOTE_PORT = (
        args.model,
        args.ssh_key_file,
        args.ssh_port,
    )
    remote.SSH_COMMAND = (["wsl"] if args.wsl else []) + [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        args.ssh_target,
        "python3",
        "-",
    ]
    script = (
        f"key_path={args.ssh_key_file!r}\nremote_port={args.ssh_port!r}\n"
        + """import json,pathlib,urllib.request
key=pathlib.Path(key_path).read_text().strip().splitlines()[0]
def get(path):
 req=urllib.request.Request('http://127.0.0.1:'+str(remote_port)+path,headers={'Authorization':'Bearer '+key})
 return json.load(urllib.request.urlopen(req,timeout=15))
try:
 props=get('/props')
 print(json.dumps({'models':[m['id'] for m in get('/v1/models')['data']],
  'context':props.get('default_generation_settings',{}).get('n_ctx'),
  'slots':props.get('total_slots'),'build':props.get('build_info')}))
except Exception as exc: print(json.dumps({'error':type(exc).__name__}))
"""
    )
    result = subprocess.run(
        remote.SSH_COMMAND, input=script.encode(), capture_output=True, timeout=40
    )
    try:
        metadata = json.loads(result.stdout)
        if result.returncode or args.model not in metadata["models"]:
            raise ValueError()
    except (ValueError, KeyError):
        raise SystemExit("Remote model metadata/authentication probe failed.") from None
    settings = Settings(
        _env_file=None, ollama_base_url="http://127.0.0.1:11434", llm_model=args.model
    )
    provider = Ollama(settings)
    provider.client.close()
    provider.client = httpx.Client(
        base_url="http://synthetic-ssh.invalid",
        transport=remote.SSHTransport(),
        timeout=330,
    )
    manifest_path = ROOT / "evaluation" / args.dataset / "manifest.json"
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    cases = [
        c for c in manifest["cases"] if args.split == "all" or c["split"] == args.split
    ]
    for c in cases:
        if (
            hashlib.sha256(
                (manifest_path.parent / c["originalFile"]).read_bytes()
            ).hexdigest()
            != c["sha256"]
        ):
            raise SystemExit("Frozen fixture changed.")
    report = {
        "kind": "visit-source-ir-extractor-ssh-series",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "split": args.split,
        "plannedRepeats": args.repeats,
        "plannedCasesPerRepeat": len(cases),
        "complete": False,
        "goldSha256": hashlib.sha256(raw_manifest).hexdigest(),
        "codeHashes": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in [
                "ai-service/medical_ai/visit.py",
                "ai-service/medical_ai/visit_review.py",
                "ai-service/medical_ai/source_ir.py",
                "ai-service/medical_ai/ollama.py",
                "scripts/evaluate_visit_ssh.py",
                "scripts/evaluate_clinical_ssh.py",
                "scripts/evaluate_visit_ingestion.py",
                "scripts/visit_semantic_metrics.py",
            ]
        },
        "recipe": {
            "modelAlias": args.model,
            "modelDigest": None,
            "promptVersion": REVIEW_PROMPT_VERSION
            if args.verify
            else VISIT_PROMPT_VERSION,
            "temperature": 0,
            "seed": 42,
            "maxTokens": settings.llm_extraction_max_tokens,
            "enableThinking": False,
            "server": metadata,
        },
        "limitations": [
            manifest["goldReview"],
            manifest["scope"],
            "Source IR -> real model annotation -> checked legacy projection only. No backend, indexing, Docker or QA acceptance.",
            "Server context applies; Ollama num_ctx is NOT forwarded. Different installation/weights; not an isolated parameter-count comparison.",
            "Model alias is operator-provided; no fresh GGUF digest or provenance verification.",
        ],
        "results": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        report["summary"] = summarize(report["results"])
        report["semanticSummary"] = summarize_semantics(report["results"])
        report["releasedSummary"] = summarize_semantics(report["results"], "released")
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    save()
    try:
        for repeat in range(1, args.repeats + 1):
            for c in cases:
                row = {
                    "case": c["id"],
                    "split": c["split"],
                    "repeat": repeat,
                    "score": score(c["statements"], []),
                    "semantic": evaluate_semantics(c["statements"], [], ""),
                    "released": evaluate_semantics(c["statements"], [], ""),
                }
                started = time.monotonic()
                try:
                    text = (
                        (manifest_path.parent / c["originalFile"])
                        .read_bytes()
                        .decode("utf-8")
                    )
                    ir = SourceIR.model_validate(
                        build_source_ir(
                            "synthetic-visit-" + c["id"],
                            [Page(text=text)],
                            "user-text-v1",
                        )
                    )
                    visit = (
                        annotate_reviewed_visit(provider, ir)
                        if args.verify
                        else annotate_visit(provider, ir)
                    )
                    extraction, _ = (
                        project_reviewed_visit(ir, visit)
                        if args.verify
                        else project_visit(ir, visit)
                    )
                    statements = [s.model_dump() for s in visit.statements]
                    row.update(
                        status="READY",
                        score=score(c["statements"], statements),
                        verifiedSources=len(statements),
                        projectedFacts=len(extraction.facts),
                    )
                    row["semantic"] = evaluate_semantics(
                        c["statements"], statements, text
                    )
                    checks = visit.model_dump().get("verifications")
                    released = (
                        statements
                        if checks is None
                        else [
                            statements[v["statementIndex"]]
                            for v in checks
                            if v["status"] == "AGREES"
                        ]
                    )
                    row["released"] = evaluate_semantics(
                        c["statements"], released, text
                    )
                    row["verificationStatuses"] = (
                        [v["status"] for v in checks] if checks is not None else None
                    )
                    row["verificationHash"] = (
                        hashlib.sha256(
                            json.dumps(
                                checks, sort_keys=True, ensure_ascii=False
                            ).encode()
                        ).hexdigest()
                        if checks is not None
                        else None
                    )
                    row["semanticHash"] = hashlib.sha256(
                        json.dumps(
                            sorted(key(s) for s in statements), ensure_ascii=False
                        ).encode()
                    ).hexdigest()
                    row["issues"] = [i.code for i in visit.issues]
                except Exception as exc:
                    row.update(status="FAILED", error=type(exc).__name__)
                row["seconds"] = round(time.monotonic() - started, 2)
                report["results"].append(row)
                save()
                print(
                    f"repeat={repeat} case={c['id']} status={row['status']} tp={row['score']['tp']}/{len(c['statements'])}",
                    flush=True,
                )
        report["complete"] = True
        save()
    finally:
        provider.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-target", required=True)
    parser.add_argument("--ssh-key-file", required=True)
    parser.add_argument("--ssh-port", type=int, default=11435)
    parser.add_argument("--model", required=True)
    parser.add_argument("--wsl", action="store_true")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Blind second reading; report withheld recall separately",
    )
    parser.add_argument(
        "--split", choices=["development", "held-out", "all"], default="development"
    )
    parser.add_argument("--repeats", type=int, choices=range(1, 11), default=3)
    parser.add_argument(
        "--dataset",
        choices=["ingestion-visits-v1", "ingestion-visits-v2"],
        default="ingestion-visits-v1",
    )
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
