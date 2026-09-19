import hashlib
import re

import pytest

from medical_ai.config import Settings
from medical_ai.main import Services


class FakeProvider:
    """Explicit deterministic CI adapter: no claim about actual model quality."""
    def __init__(self):
        self.calls = []
        self.relevant = True
        self.fail_quotes = False

    def embed(self, texts):
        self.calls.append(("embed", len(texts)))
        vectors = []
        for text in texts:
            vector = [0.0] * 32
            for token in re.findall(r"\w+", text.casefold()):
                vector[int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % 32] += 1
            vectors.append(vector)
        return vectors

    def health(self):
        return {"ready": True, "models": ["deterministic-test-adapter"]}

    def json(self, task, payload, schema=None):
        self.calls.append((task, payload))
        if "rewrite_query" in task:
            return {"query": "rewritten"}
        if "broaden_query" in task:
            return {"query": "broadened"}
        if "grade_chunks" in task:
            return {"relevant": self.relevant, "evidence": payload["chunk"] if self.relevant else ""}
        if "generate_answer" in task:
            return {"evidence": [{"citation": 1, "quote": payload["sources"][0]["text"]}], "insufficientContext": False}
        if "privacy_pass" in task:
            return {"identifiers": ([{"text": "Иванов Иван", "category": "PERSON"}]
                                    if "Иванов Иван" in payload["package"] else []), "warnings": []}
        if "extraction" in task:
            return {"documentType": "NOTE", "documentDate": None, "summary": "Наблюдение", "tags": [],
                    "facts": [{"type": "OBSERVATION", "name": "LDL", "valueNumber": 4.1, "unit": "mmol/L",
                    "assertionStatus": "CONFIRMED", "provenance": {"page": payload["pages"][0]["pageNumber"],
                    "sourceText": "invented quote" if self.fail_quotes else "LDL 4.1 mmol/L"}}]}
        raise AssertionError(task)


@pytest.fixture
def settings(tmp_path):
    sample = tmp_path / "sample_docs"
    sample.mkdir()
    return Settings(data_dir=tmp_path / "state", sample_docs_dir=sample, upload_dir=tmp_path / "uploads",
                    internal_token="test-secret", chunk_size=300, chunk_overlap=50)


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def services(settings, provider):
    return Services(settings, provider)

