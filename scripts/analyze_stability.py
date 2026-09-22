"""Render a completed or partial series and compare safe fingerprints; no model calls."""
import argparse
import json
import re
import sqlite3
from pathlib import Path

from evaluation_support import fingerprint, summarize, write_json


def first_call_difference(a, b):
    for index, (left, right) in enumerate(zip(a, b)):
        if left.get("task") != right.get("task"):
            return {"position": index, "kind": "operation-order"}
        if left.get("inputSha256") != right.get("inputSha256"):
            return {"position": index, "kind": "input", "task": left["task"]}
        if left != right:
            return {"position": index, "kind": "output-or-error", "task": left["task"]}
    if len(a) != len(b):
        return {"position": min(len(a), len(b)), "kind": "call-count"}
    return None


def analyze(root):
    state = json.loads((root / "series.json").read_text(encoding="utf-8"))
    reports = {}
    for entry in state["plan"]:
        if not re.fullmatch(r"(?:same|fresh)-\d+", entry["id"]):
            raise ValueError("Invalid run identifier")
        path = root / "runs" / (entry["id"] + ".json")
        if path.exists():
            reports[entry["id"]] = json.loads(path.read_text(encoding="utf-8"))
    summary = summarize(state["plan"], reports, state["caseIds"])
    comparisons = []
    for group in summary["groups"]:
        entries = [p for p in state["plan"] if p["group"] == group and p["id"] in reports]
        if not entries:
            continue
        reference = entries[0]["id"]
        baseline = {r["id"]: r for r in reports[reference]["results"]}
        for entry in entries[1:]:
            for row in reports[entry["id"]]["results"]:
                if row["id"] not in baseline:
                    continue
                a = baseline[row["id"]].get("diagnostics", {})
                b = row.get("diagnostics", {})
                stages = sorted(k for k in set(a.get("stages", {})) | set(b.get("stages", {}))
                                if a.get("stages", {}).get(k) != b.get("stages", {}).get(k))
                difference = first_call_difference(a.get("calls", []), b.get("calls", []))
                if stages or difference:
                    comparisons.append({"group": group, "reference": reference, "run": entry["id"],
                                        "case": row["id"], "changedStages": stages, "firstCallDifference": difference})
    indexes = {}
    if state.get("completed"):
        for name in dict.fromkeys(p["index"] for p in state["plan"]):
            if name != "shared" and not re.fullmatch(r"fresh-\d+", name):
                raise ValueError("Invalid index identifier")
            db = root / "indexes" / name / "mcp_demo/metadata.sqlite3"
            if db.exists():
                if not db.resolve().is_relative_to((root / "indexes").resolve()):
                    raise ValueError("Index outside the series")
                with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True) as connection:
                    rows = connection.execute("SELECT id,embedding FROM chunks ORDER BY id").fetchall()
                indexes[name] = {"chunks": len(rows), "vectorsSha256": fingerprint(
                    [(identifier, json.loads(vector)) for identifier, vector in rows])}
    result = {"seriesCompleted": state.get("completed", False), "summary": summary,
              "changedCaseComparisons": comparisons, "indexFingerprints": indexes,
              "limitations": "Fingerprints locate a difference; they do not alone prove its cause. "
              "Persistent same-index runs include application restart/recovery; no frozen-context replay was performed."}
    write_json(root / "analysis.json", result)
    lines = ["# Real-model stability series", "",
             "Completed." if state.get("completed") else "**INCOMPLETE: all planned runs remain in the denominator.**", "",
             "| Group | Completed / planned | Scores | Min / median / max | First ten |",
             "|---|---:|---|---|---|"]
    for group, value in summary["groups"].items():
        lines.append(f"| {group} | {value['completedRuns']} / {value['scheduledRuns']} | {value['scores']} | "
                     f"{value['min']} / {value['median']} / {value['max']} | {value['firstTenScores']} |")
    lines += ["", "## Per-question frequency", "", "| Question | Group | Passed / planned | Status | Changing stages |",
              "|---|---|---:|---|---|"]
    for group, value in summary["groups"].items():
        for case in value["cases"]:
            stages = ", ".join(k for k, n in case["stageVariants"].items() if n > 1) or "none observed"
            lines.append(f"| {case['id']} | {group} | {case['passed']} / {case['scheduled']} | {case['status']} | {stages} |")
    lines += ["", "Fingerprints and first differing calls: `analysis.json`. Source text and raw model outputs are not included.",
              "No finite series guarantees correctness or cross-device equivalence. Stable failures remain quality failures.", ""]
    (root / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("series_dir", type=Path)
    args = parser.parse_args()
    analyze(args.series_dir.resolve())
