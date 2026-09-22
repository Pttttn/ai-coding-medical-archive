"""Evaluation bookkeeping tests. These do not claim real-model stability."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from evaluate_stability import build_plan  # noqa: E402
from evaluation_support import CRITERIA, ObservedProvider, diagnostics, summarize, write_json  # noqa: E402


def report(ids, passes, complete=True):
    return {"completed": complete, "results": [dict(id=case, passed=case in passes,
            **{key: case in passes for key in CRITERIA}) for case in ids]}


def test_failures_partial_runs_and_missing_runs_remain_in_denominator():
    plan = build_plan(3, 1)
    result = summarize(plan, {"same-01": report(["a", "b"], ["a"]),
                             "same-02": report(["a"], ["a"], False),
                             "fresh-01": report(["a", "b"], ["a", "b"])}, ["a", "b"])
    same = result["groups"]["same-index"]
    assert same["scores"] == [1, 1, 0]
    assert (same["min"], same["median"], same["max"]) == (0, 1, 1)
    assert same["completedRuns"] == 1 and same["scheduledRuns"] == 3
    assert same["cases"][0]["passRate"] == 2 / 3
    assert same["cases"][0]["status"] == "missing"
    assert not same["allQuestionsPassedEveryRun"]
    assert not result["groups"]["fresh-index"]["firstTenPassedEveryRun"]


def test_first_ten_gate_requires_every_scheduled_complete_run():
    ids = [str(i) for i in range(21)]
    data = {entry["id"]: report(ids, ids) for entry in build_plan(2, 1)}
    data["same-02"]["results"][0]["passed"] = False
    result = summarize(build_plan(2, 1), data, ids)
    same = result["groups"]["same-index"]
    assert same["scores"] == [21, 20] and same["median"] == 20.5
    assert same["firstTenScores"] == [10, 9] and not same["firstTenPassedEveryRun"]
    assert same["cases"][0]["status"] == "unstable"
    assert result["groups"]["fresh-index"]["firstTenPassedEveryRun"]


@pytest.mark.parametrize("ids", [["a", "a"], ["b", "a"], ["a", "other"]])
def test_duplicate_reordered_or_unknown_rows_cannot_inflate_score(ids):
    result = summarize(build_plan(1, 1), {"same-01": report(ids, ids)}, ["a", "b"])
    assert result["groups"]["same-index"]["scores"] == [0]
    assert result["groups"]["same-index"]["completedRuns"] == 0


def test_observer_records_only_hashes_and_does_not_change_requests():
    secret = "Synthetic PRIVATE-CANARY-42"

    class Provider:
        def json(self, task, payload, schema):
            assert payload == {"text": secret}
            return {"answer": secret}

        def embed(self, texts):
            assert texts == [secret]
            return [[0.123, 0.456]]

    observed = ObservedProvider(Provider())
    assert observed.json("TASK: generate_answer. Instructions", {"text": secret}, {}) == {"answer": secret}
    assert observed.embed([secret]) == [[0.123, 0.456]]
    assert secret not in json.dumps(observed.calls)
    assert "0.123" not in json.dumps(observed.calls)
    assert all(len(c["outputSha256"]) == 64 for c in observed.calls)


def test_diagnostics_ignore_random_refs_but_detect_source_changes():
    raw = {"answer": "Synthetic private text", "sources": [{"source": "synthetic/private.md"}],
           "insufficientContext": False, "trace": [{"node": "retrieve", "chunkIds": ["secret-id"]}]}
    a = diagnostics(raw, [], {"answer": "checked", "responseRef": "random-a"})
    b = diagnostics(raw, [], {"answer": "checked", "responseRef": "random-b"})
    assert a == b
    assert "private" not in json.dumps(a) and "secret-id" not in json.dumps(a)
    raw["sources"] = []
    assert diagnostics(raw, [], {"answer": "checked"}) != a


def test_atomic_report_replaces_only_target_and_leaves_valid_json(tmp_path):
    path = tmp_path / "run.json"
    write_json(path, {"completed": False})
    write_json(path, {"completed": True})
    assert json.loads(path.read_text()) == {"completed": True}
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("mismatch", [False, True])
def test_runner_isolates_indexes_removes_external_override_and_checks_profile(tmp_path, monkeypatch, mismatch):
    import subprocess
    import evaluate_stability as runner

    root = tmp_path / "repo"
    (root / "evaluation").mkdir(parents=True)
    ids = [str(i) for i in range(21)]
    (root / "evaluation/questions.json").write_text(json.dumps([{"id": i} for i in ids]))
    output = tmp_path / "series"
    expected = {"models": {"model": "digest", "embedding": "digest"}}

    class Response:
        def json(self):
            return {"models": [{"name": name, "digest": "digest", "size_vram": 0} for name in expected["models"]]}

    class Provider:
        client = None

        def __init__(self):
            self.client = self

        def get(self, path):
            return Response()

        def close(self):
            pass

        def json(self, *args):
            return {"query": "ready"}

        def embed(self, texts):
            return [[0.1]]

    calls = []

    def child(command, env, **kwargs):
        assert "MCP_DEMO_DIR" not in env
        calls.append(env["DATA_DIR"])
        target = Path(command[-1])
        data = report(ids, ids)
        data["manifest"] = expected
        write_json(target, data)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setenv("MCP_DEMO_DIR", str(tmp_path / "must-not-touch"))
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "Ollama", lambda settings: Provider())
    monkeypatch.setattr(runner, "manifest", lambda *a: expected)
    monkeypatch.setattr(runner.subprocess, "run", child)
    argv = ["evaluate_stability.py", "--output-dir", str(output), "--execution", "cpu",
            "--same-index-runs", "2", "--fresh-index-runs", "1"]
    if mismatch:
        profile = tmp_path / "wrong.json"
        profile.write_text('{"models":{}}')
        argv += ["--profile", str(profile)]
    monkeypatch.setattr(sys, "argv", argv)
    assert runner.main() == (1 if mismatch else 0)
    result = json.loads((output / "series.json").read_text())
    if mismatch:
        assert not calls
        assert result["failureCode"] == "PROFILE_MISMATCH"
        assert result["summary"]["groups"]["same-index"]["scores"] == [0, 0]
    else:
        assert calls[0] == calls[1] and calls[1] != calls[2]
        assert all(Path(c).is_relative_to(output) for c in calls)
        assert result["completed"]
        assert result["summary"]["groups"]["same-index"]["scores"] == [21, 21]
    # Never reuse/overwrite a previous series, including a failed one.
    with pytest.raises(FileExistsError):
        runner.main()
