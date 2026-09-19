#!/bin/sh
set -eu
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_NO_CLOUD=1
ollama serve > /tmp/ollama-init.log 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT INT TERM
attempt=0
until ollama list >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -gt 120 ]; then echo 'Model provisioning server did not become ready'; exit 1; fi
  sleep 1
done
ollama pull "$LLM_MODEL"
ollama pull "$EMBEDDING_MODEL"
echo 'Local model provisioning complete; archive data was not mounted.'
