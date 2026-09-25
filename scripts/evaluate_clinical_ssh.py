"""Synthetic-only matrix over SSH; the credential never leaves the model host."""
import argparse
import json
import subprocess
import sys
import httpx
import evaluate_clinical_matrix as matrix
MODEL = None
SSH_COMMAND = None
KEY_FILE = None
REMOTE_PORT = None
METADATA = {}

class SSHTransport(httpx.BaseTransport):
    def __init__(self):
        self.local = httpx.Client(base_url='http://127.0.0.1:11434', timeout=300, trust_env=False)
    def close(self):
        self.local.close()

    def handle_request(self, request):
        path = request.url.path
        if path == '/api/tags':
            data = self.local.get(path).json()
            data['models'].append({'name': MODEL, 'digest': METADATA.get('modelSha256') or 'unavailable-remote-gguf'})
            return httpx.Response(200, json=data)
        if path != '/api/chat':
            result = self.local.request(request.method, path, content=request.content, headers={'Content-Type': 'application/json'})
            return httpx.Response(result.status_code, content=result.content)
        body = json.loads(request.content)
        options = body.get('options', {})
        payload = {'model': MODEL, 'messages': body['messages'], 'temperature': options.get('temperature', 0),
                   'seed': options.get('seed', 42), 'max_tokens': options.get('num_predict', 4096), 'stream': False,
                   'chat_template_kwargs': {'enable_thinking': False}}
        fmt = body.get('format')
        if isinstance(fmt, dict):
            payload['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'evidence', 'schema': fmt}}
        if body.get('tools'):
            payload['tools'] = body['tools']
        script = f"key_path={KEY_FILE!r}\nremote_port={REMOTE_PORT!r}\npayload_json={json.dumps(payload, ensure_ascii=True)!r}\n" + """import json,pathlib,urllib.request
key=pathlib.Path(key_path).read_text().strip().splitlines()[0]
payload=json.loads(payload_json)
req=urllib.request.Request('http://127.0.0.1:'+str(remote_port)+'/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
try:
 with urllib.request.urlopen(req,timeout=300) as response: print(response.read().decode())
except Exception as exc:
 print(json.dumps({'transportError':type(exc).__name__}))
"""
        result = subprocess.run(SSH_COMMAND,
                                input=script.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=320)
        if result.returncode:
            return httpx.Response(503, json={'error': 'SSH_FAILED'})
        data = json.loads(result.stdout)
        if 'transportError' in data:
            return httpx.Response(503, json={'error': data['transportError']})
        choice = data['choices'][0]
        message = choice['message']
        message['content'] = message.get('content') or ''
        return httpx.Response(200, json={'message': message, 'done_reason': choice['finish_reason'], 'done': True})

class RemoteProvider(matrix.BenchmarkProvider):
    def __init__(self, settings):
        super().__init__(settings)
        self.benchmark_metadata = METADATA
        self.client.close()
        self.client = httpx.Client(base_url='http://synthetic-ssh.invalid', transport=SSHTransport(), timeout=330)

matrix.BenchmarkProvider = RemoteProvider
def main():
    global MODEL, SSH_COMMAND, KEY_FILE, REMOTE_PORT, METADATA
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--ssh-target', required=True)
    parser.add_argument('--ssh-key-file', required=True)
    parser.add_argument('--ssh-port', type=int, default=11435, help='Loopback model HTTP port on the remote host')
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--model-sha256', help='Previously measured GGUF SHA256; omitted means unavailable')
    args, remaining = parser.parse_known_args()
    if args.ssh_target.startswith('-') or not 1 <= args.ssh_port <= 65535:
        parser.error('Invalid SSH destination or model port.')
    if '--models' not in remaining:
        parser.error('Specify exactly one remote model using --models.')
    model_index = remaining.index('--models') + 1
    if model_index >= len(remaining) or remaining[model_index].startswith('-'):
        parser.error('Missing remote model.')
    MODEL = remaining[model_index]
    if model_index + 1 < len(remaining) and not remaining[model_index + 1].startswith('-'):
        parser.error('Only one remote model per invocation.')
    if 'tools' in remaining:
        parser.error('SSH adapter currently supports retrieval/scan profiles, not tool-call conversation translation.')
    KEY_FILE, REMOTE_PORT = args.ssh_key_file, args.ssh_port
    SSH_COMMAND = (['wsl'] if args.wsl else []) + ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', args.ssh_target, 'python3', '-']
    probe = f"key_path={KEY_FILE!r}\nremote_port={REMOTE_PORT!r}\n" + """import json,pathlib,urllib.request
key=pathlib.Path(key_path).read_text().strip().splitlines()[0]
def get(path):
 req=urllib.request.Request('http://127.0.0.1:'+str(remote_port)+path,headers={'Authorization':'Bearer '+key})
 return json.load(urllib.request.urlopen(req,timeout=15))
try:
 models=get('/v1/models')['data']
 props=get('/props')
 print(json.dumps({'models':[{'id':m['id'],'meta':m.get('meta')} for m in models], 'context':props.get('default_generation_settings',{}).get('n_ctx'), 'slots':props.get('total_slots'), 'build':props.get('build_info')}))
except Exception as exc: print(json.dumps({'error':type(exc).__name__}))
"""
    result = subprocess.run(SSH_COMMAND, input=probe.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
    try:
        remote = json.loads(result.stdout)
        if result.returncode or not any(m['id'] == MODEL for m in remote['models']):
            raise ValueError()
    except (ValueError, KeyError):
        raise SystemExit('Remote model metadata/authentication probe failed.') from None
    if args.model_sha256 and (len(args.model_sha256) != 64 or any(c not in '0123456789abcdef' for c in args.model_sha256)):
        parser.error('Invalid model SHA256.')
    METADATA = {'transport': 'SSH stdio / remote loopback llama.cpp', 'modelSha256': args.model_sha256,
                'modelSha256Origin': 'operator-supplied measurement', 'server': remote,
                'embeddingEndpoint': 'local Ollama', 'requestedThinking': False,
                'contextNote': 'Ollama num_ctx is not forwarded; the server context applies.'}
    sys.argv = [sys.argv[0]] + remaining
    matrix.BenchmarkProvider = RemoteProvider
    matrix.main()

if __name__ == '__main__':
    main()
