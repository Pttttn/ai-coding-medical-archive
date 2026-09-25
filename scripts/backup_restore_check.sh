#!/usr/bin/env bash
# Real Docker check of scripts/archive_backup.py on synthetic seed data only:
# migrations + seed in a throwaway project, encrypted backup, restore into a second empty project,
# completeness verification, backend start on the restored copy, and refusal to overwrite.
# The AI service and Ollama are not started; the ai_archive volume holds a synthetic placeholder,
# so this proves the backup mechanics, not RAG quality. Both projects are removed on exit.
set -euo pipefail
cd "$(dirname "$0")/.."

SOURCE=lma-backup-check
TARGET=lma-restore-check
BACKEND_IMAGE=${BACKEND_IMAGE:-local-medical-archive-backend}
WORK=$(mktemp -d)
OVERRIDE="$WORK/override.yaml"
cat > "$OVERRIDE" <<EOF
services:
  backend:
    image: $BACKEND_IMAGE
    depends_on: !override
      postgres:
        condition: service_healthy
EOF
compose() { local project=$1; shift; docker compose -p "$project" -f compose.yaml -f "$OVERRIDE" "$@"; }
cleanup() {
  compose "$SOURCE" down -v --remove-orphans >/dev/null 2>&1 || true
  compose "$TARGET" down -v --remove-orphans >/dev/null 2>&1 || true
  docker volume rm "${SOURCE}_ai_archive" "${TARGET}_ai_archive" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT
cleanup_needed=$(docker volume ls -q --filter "label=com.docker.compose.project=$SOURCE")
[ -z "$cleanup_needed" ] || { echo "stale $SOURCE volumes exist" >&2; exit 1; }

count() { compose "$1" exec -T postgres psql -U archive -d archive -Atc "$2" 2>/dev/null || true; }
wait_documents() {
  for _ in $(seq 1 90); do
    [ "$(count "$1" 'select count(*) from documents')" = "$2" ] && return 0
    sleep 2
  done
  echo "project $1 did not reach $2 documents" >&2; return 1
}

compose "$SOURCE" up -d --no-build postgres backend
wait_documents "$SOURCE" 32
docker volume create --label "com.docker.compose.project=$SOURCE" \
  --label com.docker.compose.volume=ai_archive "${SOURCE}_ai_archive" >/dev/null
docker run --rm --network none -v "${SOURCE}_ai_archive:/v" --entrypoint sh postgres:17-alpine \
  -c 'mkdir -p /v/archive/chroma && echo synthetic-placeholder > /v/archive/metadata.sqlite3'

printf 'synthetic-check-passphrase\n' > "$WORK/passphrase"
python3 scripts/archive_backup.py backup -p "$SOURCE" -f compose.yaml -f "$OVERRIDE" \
  -o "$WORK/backup.tar" --passphrase-file "$WORK/passphrase"
test "$(stat -c %a "$WORK/backup.tar")" = 600
! tar -xOf "$WORK/backup.tar" | grep -aq "storagePath"
python3 scripts/archive_backup.py verify "$WORK/backup.tar" --passphrase-file "$WORK/passphrase"

python3 scripts/archive_backup.py restore -p "$TARGET" -f compose.yaml -f "$OVERRIDE" \
  "$WORK/backup.tar" --passphrase-file "$WORK/passphrase"
compose "$TARGET" up -d --no-build postgres backend
wait_documents "$TARGET" 32
for _ in $(seq 1 60); do
  total=$(compose "$TARGET" exec -T backend node -e \
    "fetch('http://127.0.0.1:3000/api/documents?pageSize=100').then(r=>r.json()).then(j=>console.log(j.total))" \
    2>/dev/null || true)
  [ "$total" = 32 ] && break
  sleep 2
done
[ "$total" = 32 ] || { echo "restored API did not list 32 documents" >&2; exit 1; }
[ "$(count "$TARGET" 'select count(*) from migrations')" = "$(count "$SOURCE" 'select count(*) from migrations')" ]

compose "$TARGET" stop >/dev/null
if python3 scripts/archive_backup.py restore -p "$TARGET" -f compose.yaml -f "$OVERRIDE" \
    "$WORK/backup.tar" --passphrase-file "$WORK/passphrase"; then
  echo "restore over a non-empty project must be refused" >&2; exit 1
fi
echo "backup/restore check passed"
