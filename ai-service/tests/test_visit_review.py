import json
from pathlib import Path

import pytest

from medical_ai.errors import ServiceError
from medical_ai.source_ir import SourceIR, canonical_hash
from medical_ai.visit import Candidate, Visit
from medical_ai.visit_review import ReviewedVisit, project_reviewed_visit, review_visit, verification

ROOT = Path(__file__).resolve().parents[2]


def fixture():
    f = json.loads((ROOT / "contracts/visit-assertions-v2.synthetic.json").read_text(encoding="utf-8"))
    return f, SourceIR.model_validate(f["sourceIR"]), ReviewedVisit.model_validate(f["visit"])


def original(visit):
    body = visit.model_dump(exclude={"verifications", "reviewVersion", "artifactHash"})
    body["schemaVersion"] = "visit-assertions-v1"
    return Visit(**body, artifactHash=canonical_hash(body))


def test_shared_contract_and_disagreement_do_not_publish_confirmed_taking():
    f, ir, v = fixture()
    e, warnings = project_reviewed_visit(ir, v)
    assert e.model_dump(mode="json") == f["extraction"]
    assert e.facts[5].type == "OBSERVATION" and e.facts[5].assertionStatus == "UNKNOWN"
    assert v.statements[5].medicationState == "TAKING"
    assert v.verifications[5].alternative.medicationState == "NOT_STARTED"
    assert "не является медицинской проверкой" in warnings[-1]
    assert ReviewedVisit.model_json_schema() == json.loads(
        (ROOT / "contracts/visit-assertions-v2.schema.json").read_text()
    )


@pytest.mark.parametrize("tamper", ["verdict", "anchor", "index", "missing", "null"])
def test_recomputed_hash_cannot_hide_invalid_review(tamper):
    _, ir, v = fixture()
    if tamper == "verdict":
        v.verifications[5].status = "AGREES"
    if tamper == "anchor":
        v.verifications[5].alternative.source.startByte += 1
    if tamper == "index":
        v.verifications[5].statementIndex = 0
    if tamper == "missing":
        v.verifications.pop()
    if tamper == "null":
        v.verifications[0].alternative = None
    v.artifactHash = canonical_hash(v.model_dump(exclude={"artifactHash"}))
    with pytest.raises(ValueError):
        project_reviewed_visit(ir, v)


def test_second_reading_does_not_receive_previous_classification():
    _, ir, v = fixture()

    class Model:
        def json(self, task, payload, schema):
            assert "no prior classification" in task
            assert all(set(t) == {"statementIndex", "name", "blockId", "anchor"} for t in payload["targets"])
            checks = []
            for t in payload["targets"]:
                alt = v.verifications[t["statementIndex"]].alternative
                checks.append(
                    {
                        "statementIndex": t["statementIndex"],
                        "interpretation": alt.model_dump(exclude={"source", "contextSource", "contextText"}),
                    }
                )
            return {"checks": checks}

    checked = review_visit(Model(), ir, original(v))
    assert checked == v


def test_missing_duplicate_review_targets_are_unresolved_not_agreement():
    _, ir, v = fixture()

    class Model:
        calls = 0

        def json(self, *args):
            self.calls += 1
            return {"checks": []}

    model = Model()
    checked = review_visit(model, ir, original(v))
    assert len(checked.verifications) == len(v.statements)
    assert all(c.status == "UNRESOLVED" for c in checked.verifications)
    assert all(
        f.assertionStatus == "UNKNOWN" and f.type == "OBSERVATION"
        for f in project_reviewed_visit(ir, checked)[0].facts
    )
    assert model.calls == 14


def test_unavailable_verifier_raises_instead_of_publishing_raw_first_pass():
    _, ir, v = fixture()

    class Model:
        def json(self, *args):
            raise ServiceError("MODEL_UNAVAILABLE", "fixed")

    with pytest.raises(ServiceError):
        review_visit(Model(), ir, original(v))


def test_reviewer_cannot_replace_anchor_with_neighbouring_event():
    _, ir, v = fixture()
    c = Candidate.model_validate(
        v.statements[0].model_dump(exclude={"source", "contextSource", "contextText"})
    )
    assert verification(5, v.statements[5], c, ir).status == "UNRESOLVED"
