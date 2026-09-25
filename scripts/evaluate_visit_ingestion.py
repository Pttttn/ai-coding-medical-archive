"""Frozen original-upload VISIT series. Gold never enters the model; failures stay in denominator."""

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

from evaluate_ingestion import request

ROOT = Path(__file__).resolve().parents[1]
FIELDS = (
    "name",
    "kind",
    "subject",
    "assertion",
    "medicationState",
    "temporality",
    "sourceText",
)
CLASSES = {
    "subject": ["PATIENT", "FAMILY", "OTHER", "UNKNOWN"],
    "assertion": [
        "CONFIRMED",
        "SUSPECTED",
        "NEGATED",
        "NOT_CONFIRMED",
        "RULED_OUT",
        "UNKNOWN",
    ],
    "medicationState": [
        "NOT_APPLICABLE",
        "PRESCRIBED",
        "TAKING",
        "NOT_STARTED",
        "NOT_TAKING",
        "STOPPED",
        "UNKNOWN",
    ],
    "temporality": ["CURRENT", "HISTORICAL", "FUTURE", "UNKNOWN"],
}


def key(row, fields=FIELDS):
    return tuple(
        row.get(f, "").casefold() if f == "name" else row.get(f) for f in fields
    )


def score(gold, actual):
    def counts(expected, found, fields):
        tp = sum(
            (
                Counter(key(r, fields) for r in expected)
                & Counter(key(r, fields) for r in found)
            ).values()
        )
        return {"tp": tp, "fp": len(found) - tp, "fn": len(expected) - tp}

    classes = {}
    for field, labels in CLASSES.items():
        classes[field] = {
            label: counts(
                [r for r in gold if r[field] == label],
                [r for r in actual if r[field] == label],
                ("name", "sourceText", field),
            )
            for label in labels
        }
    critical = 0
    for found in actual:
        expected = [r for r in gold if key(r, ("name",)) == key(found, ("name",))]
        if not expected:
            # Unmatched claims count as FP; cannot establish their safety against a matching gold.
            continue
        if (
            found["subject"] == "PATIENT"
            and found["assertion"] == "CONFIRMED"
            and not any(
                r["subject"] == "PATIENT" and r["assertion"] == "CONFIRMED"
                for r in expected
            )
        ):
            critical += 1
        if (
            found["kind"] == "MEDICATION"
            and found["medicationState"] == "TAKING"
            and not any(
                r["subject"] == found["subject"] and r["medicationState"] == "TAKING"
                for r in expected
            )
        ):
            critical += 1
    return {
        **counts(gold, actual, FIELDS),
        "classes": classes,
        "criticalPromotions": critical,
    }


def summarize(rows):
    repeats = []
    for repeat in sorted({r["repeat"] for r in rows}):
        subset = [r for r in rows if r["repeat"] == repeat]
        out = {
            "repeat": repeat,
            "cases": len(subset),
            "ready": sum(
                r.get("status") == "READY" and not r.get("error") for r in subset
            ),
            **{
                k: sum(r["score"][k] for r in subset)
                for k in ["tp", "fp", "fn", "criticalPromotions"]
            },
            "macroF1": {},
        }
        for field, labels in CLASSES.items():
            f1 = []
            for label in labels:
                totals = {
                    k: sum(r["score"]["classes"][field][label][k] for r in subset)
                    for k in ["tp", "fp", "fn"]
                }
                denominator = 2 * totals["tp"] + totals["fp"] + totals["fn"]
                if denominator:
                    f1.append(2 * totals["tp"] / denominator)
            out["macroF1"][field] = round(sum(f1) / len(f1), 6) if f1 else None
        repeats.append(out)
    return repeats


def run(args):
    if args.output.exists():
        raise SystemExit("Refusing to overwrite previous attempt.")
    if request(args.base, "/documents?pageSize=1&deleted=all")["total"]:
        raise SystemExit(
            "Requires an EMPTY dedicated SEED_ENABLED=false archive, including trash."
        )
    manifest_path = ROOT / "evaluation/ingestion-visits-v1/manifest.json"
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    cases = [
        c for c in manifest["cases"] if args.split == "all" or c["split"] == args.split
    ]
    for case in cases:
        if (
            hashlib.sha256(
                (manifest_path.parent / case["originalFile"]).read_bytes()
            ).hexdigest()
            != case["sha256"]
        ):
            raise SystemExit("Frozen original changed.")
    report = {
        "kind": "original-upload-visit-series",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "goldSha256": hashlib.sha256(raw_manifest).hexdigest(),
        "split": args.split,
        "plannedRepeats": args.repeats,
        "plannedCasesPerRepeat": len(cases),
        "complete": False,
        "codeHashes": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in [
                "scripts/evaluate_visit_ingestion.py",
                "ai-service/medical_ai/visit.py",
                "ai-service/medical_ai/ollama.py",
                "ai-service/medical_ai/source_ir.py",
                "backend/src/visit.ts",
            ]
        },
        "limitations": [
            manifest["goldReview"],
            manifest["scope"],
            "First upload then explicit reprocess with new jobs/extraction IDs; same installation/index, not independent deployments.",
            "Exact source sentence tuple with case-insensitive name. Missing/failed outputs are FN, duplicates are FP. No clinical validity claim.",
        ],
        "results": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        report["summary"] = summarize(report["results"])
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    save()
    ids, runs = {}, {}
    for repeat in range(1, args.repeats + 1):
        for case in cases:
            row = {
                "case": case["id"],
                "split": case["split"],
                "repeat": repeat,
                "expected": len(case["statements"]),
                "score": score(case["statements"], []),
            }
            start = time.monotonic()
            try:
                if case["id"] in ids:
                    queued = request(
                        args.base, "/documents/" + ids[case["id"]] + "/reprocess", {}
                    )
                else:
                    raw = (
                        (manifest_path.parent / case["originalFile"])
                        .read_bytes()
                        .decode("utf-8")
                    )
                    queued = request(
                        args.base,
                        "/documents/note",
                        {"title": "SYNTHETIC visit evaluation", "text": raw},
                    )
                    ids[case["id"]] = queued["id"]
                deadline = time.monotonic() + 900
                while True:
                    job = request(args.base, "/jobs/" + queued["jobId"])
                    if (
                        job["status"] in {"READY", "FAILED", "SUPERSEDED"}
                        or time.monotonic() > deadline
                    ):
                        break
                    time.sleep(0.5)
                doc = request(args.base, "/documents/" + ids[case["id"]])
                row["status"] = doc["status"]
                if (
                    job["status"] != "READY"
                    or doc["status"] != "READY"
                    or doc["latestJob"]["id"] != queued["jobId"]
                ):
                    raise RuntimeError("ProcessingIncomplete")
                extraction = doc.get("extraction") or {}
                if not extraction.get("id") or extraction["id"] == runs.get(case["id"]):
                    raise RuntimeError("NewExtractionRequired")
                runs[case["id"]] = extraction["id"]
                row["newExtractionRun"] = True
                row["recipe"] = {
                    k: extraction.get(k)
                    for k in [
                        "model",
                        "modelDigest",
                        "promptVersion",
                        "schemaVersion",
                        "parserVersion",
                    ]
                }
                row["profile"] = doc.get("extractionProfile")
                row["processingRecipe"] = doc.get("processingRecipe")
                artifact = doc.get("visit")
                row["artifactPresent"] = artifact is not None
                if artifact is None:
                    raise ValueError("VisitArtifactMissing")
                ir = request(args.base, "/documents/" + doc["id"] + "/source-ir")[
                    "content"
                ]
                if (
                    artifact["sourceIRHash"] != ir["irHash"]
                    or artifact["sourceHash"] != ir["sourceHash"]
                ):
                    raise ValueError("WrongSourceRevision")
                for s in artifact["statements"]:
                    for span_key, text_key in [
                        ("source", "sourceText"),
                        ("contextSource", "contextText"),
                    ]:
                        span = s[span_key]
                        actual = (
                            ir["pages"][span["pageIndex"]]["text"]
                            .encode()[span["startByte"] : span["endByte"]]
                            .decode()
                        )
                        if actual != s[text_key]:
                            raise ValueError("WrongSourceSpan")
                row["verifiedSources"] = len(artifact["statements"])
                row["score"] = score(case["statements"], artifact["statements"])
                row["issues"] = dict(Counter(i["code"] for i in artifact["issues"]))
                # Order is immaterial; repeats compare a multiset, preserving duplicates.
                semantics = sorted(key(s) for s in artifact["statements"])
                row["semanticHash"] = hashlib.sha256(
                    json.dumps(semantics, ensure_ascii=False).encode()
                ).hexdigest()
            except HTTPError as exc:
                row["error"], row["httpStatus"] = "HTTPError", exc.code
            except Exception as exc:
                row["error"] = type(exc).__name__
            row["seconds"] = round(time.monotonic() - start, 2)
            report["results"].append(row)
            save()
            print(
                f"repeat={repeat} case={case['id']} status={row.get('status')} tp={row['score']['tp']}/{row['expected']} error={row.get('error')}",
                flush=True,
            )
    report["complete"] = True
    save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split", choices=["development", "held-out", "all"], default="development"
    )
    parser.add_argument("--repeats", type=int, choices=range(1, 11), default=3)
    run(parser.parse_args())
