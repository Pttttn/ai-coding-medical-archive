"""Read-only checks of the local demo runtime and its network boundaries."""
import argparse
import json
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:3000")
    parser.add_argument("--mode", choices=["container", "host"], default="container")
    parser.add_argument("--output", help="Write a separate report without replacing historical results")
    parser.add_argument("--project", help="Compose project name, for an isolated deployment")
    args = parser.parse_args()
    compose = ["docker", "compose", "-f", "compose.yaml"]
    if args.project:
        compose += ["-p", args.project]
    if args.mode == "host":
        compose += ["-f", "compose.host-ollama.yaml"]
    results = []

    def run(service, executable, code):
        result = subprocess.run(compose + ["exec", "-T", service, executable, "-c" if executable == "python" else "-e", code], capture_output=True, text=True, timeout=30, check=True)
        return json.loads(result.stdout)

    with urllib.request.urlopen(args.api + "/api/health", timeout=10) as response:
        assert json.load(response)["status"] == "ok"
    results.append({"check": "API health", "passed": True})
    state = run("ai", "python", "import json,urllib.request; from medical_ai.config import Settings; print(json.dumps({'provider':Settings().ollama_base_url,'health':json.load(urllib.request.urlopen('http://localhost:8001/health'))}))")
    assert state["provider"] == ("http://ollama:11434" if args.mode == "container" else "http://host-ollama:11434")
    assert state["health"]["ready"], state
    results.append({"check": "local model readiness", "passed": True, **state})
    blocked = run("ai", "python", "import socket,json; s=socket.socket();s.settimeout(2); result=s.connect_ex(('1.1.1.1',443));s.close();print(json.dumps({'blocked':result!=0,'socketCode':result}))")
    assert blocked["blocked"], blocked
    results.append({"check": "AI external egress blocked", "passed": True, **blocked})
    blocked = run("backend", "node", "fetch('https://1.1.1.1',{signal:AbortSignal.timeout(2000)}).then(()=>{console.log(JSON.stringify({blocked:false}))}).catch(()=>console.log(JSON.stringify({blocked:true})))")
    assert blocked["blocked"], blocked
    results.append({"check": "backend external egress blocked", "passed": True})
    for service in (["gateway", "host-ollama"] if args.mode == "host" else ["gateway"]):
        rules = subprocess.run(compose + ["exec", "-T", service, "iptables", "-S", "OUTPUT"], capture_output=True, text=True, timeout=10, check=True).stdout
        assert "-P OUTPUT DROP" in rules, rules
        attempt = subprocess.run(compose + ["exec", "-T", service, "wget", "-q", "-T", "2", "-O", "/dev/null", "http://1.1.1.1"], capture_output=True, timeout=10)
        assert attempt.returncode != 0
        results.append({"check": service + " external egress blocked", "passed": True, "policy": "OUTPUT DROP", "exitCode": attempt.returncode})
    if args.mode == "host":
        denied = run("ai", "python", "import json,urllib.request,urllib.error\ntry:\n urllib.request.urlopen(urllib.request.Request('http://host-ollama:11434/api/pull',data=b'{}'),timeout=5)\n print(json.dumps({'status':200}))\nexcept urllib.error.HTTPError as e:\n print(json.dumps({'status':e.code}))")
        assert denied["status"] == 403, denied
        results.append({"check": "host proxy rejects model downloads", "passed": True, **denied})
    target = Path(args.output) if args.output else Path("docs/evaluation") / ("runtime-" + args.mode + ".json")
    target.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "mode": args.mode, "checks": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS {len(results)} runtime checks ({args.mode})")


if __name__ == "__main__":
    main()
