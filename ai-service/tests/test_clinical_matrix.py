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
    provider.generation_calls = 0
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {'message': {'role': 'assistant', 'tool_calls': [{'function': {'name': 'read_documents', 'arguments': {'ids': ['excluded']}}}]}}
    provider.client = SimpleNamespace(post=lambda *args, **kwargs: Response())
    corpus = ExperimentalCorpus(services.archive, provider, 'tools', [])
    with pytest.raises(ValueError, match='out-of-scope'):
        corpus.retrieve('question', 12, ['allowed'])


def test_published_aggregate_never_contains_response_content():
    from analyze_clinical import aggregate
    import json
    profile = {'model': 'test', 'strategy': 'scan', 'runs': [{'run': 1, 'results': [
        {'id': 'case', 'passed': True, 'seconds': 1, 'response': {'answer': 'PRIVATE_SENTINEL',
        'sources': [{'text': 'PRIVATE_SENTINEL', 'documentId': 'PRIVATE_ID'}], 'coverage': {'complete': True}}}
    ]}]}
    result = aggregate(profile)
    assert result['runs'][0]['passed'] == 1
    assert 'PRIVATE_' not in json.dumps(result)

def test_ssh_transport_keeps_key_remote_and_preserves_output_limits(monkeypatch):
    import json
    import httpx
    import evaluate_clinical_ssh as remote
    monkeypatch.setattr(remote, 'MODEL', 'synthetic-model')
    monkeypatch.setattr(remote, 'KEY_FILE', '/etc/test-model.keys')
    monkeypatch.setattr(remote, 'REMOTE_PORT', 11435)
    monkeypatch.setattr(remote, 'SSH_COMMAND', ['ssh', 'test-host', 'python3', '-'])
    seen = []
    def run(command, **kwargs):
        seen.append((command, kwargs['input'].decode()))
        return SimpleNamespace(returncode=0, stdout=json.dumps({'choices': [{'message': {'role': 'assistant', 'content': '{"quotes":[]}'}, 'finish_reason': 'length'}]}).encode())
    monkeypatch.setattr(remote.subprocess, 'run', run)
    transport = remote.SSHTransport()
    with httpx.Client(base_url='http://test', transport=transport) as client:
        response = client.post('/api/chat', json={'messages': [{'role': 'user', 'content': 'synthetic KEY_PATH MODEL_PORT PAYLOAD'}],
            'format': {'type': 'object'}, 'options': {'num_predict': 4096, 'seed': 42}}).json()
    assert response['done_reason'] == 'length'
    assert seen[0][0] == ['ssh', 'test-host', 'python3', '-']
    assert '/etc/test-model.keys' in seen[0][1]
    import ast
    tree = ast.parse(seen[0][1])
    payload = json.loads(ast.literal_eval(tree.body[2].value))
    assert payload['messages'][0]['content'] == 'synthetic KEY_PATH MODEL_PORT PAYLOAD'
    assert payload['max_tokens'] == 4096
    assert payload['response_format']['type'] == 'json_schema'
