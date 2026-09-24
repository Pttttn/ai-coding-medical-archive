import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from evaluate_clinical_matrix import ExperimentalCorpus  # noqa: E402


def test_bm25_dense_and_hybrid_stay_in_allowed_corpus(services, provider):
    services.archive.index_document('allowed', 'a.md', 1, 'LDL high result.')
    services.archive.index_document('excluded', 'b.md', 1, 'LDL high private excluded.')
    for strategy in ['bm2512', 'dense12', 'hybrid12', 'scan']:
        corpus = ExperimentalCorpus(services.archive, provider, strategy, [])
        result = corpus.retrieve('LDL', 12, ['allowed'])
        assert {d.metadata['documentId'] for d in result} == {'allowed'}


def test_tool_agent_rejects_read_outside_eligible_period(services, provider, settings):
    services.archive.index_document('allowed', 'a.md', 1, 'LDL high result.')
    provider.settings = settings
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {'message': {'role': 'assistant', 'tool_calls': [{'function': {'name': 'read_documents', 'arguments': {'ids': ['excluded']}}}]}}
    provider.client = SimpleNamespace(post=lambda *args, **kwargs: Response())
    corpus = ExperimentalCorpus(services.archive, provider, 'tools', [])
    with pytest.raises(ValueError, match='out-of-scope'):
        corpus.retrieve('question', 12, ['allowed'])
