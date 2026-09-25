"""Consistent backup, integrity check and verified restore of a Local Medical Archive Compose installation.

The backup covers the three stores that hold archive state: PostgreSQL (``postgres_data``), the
original uploads (``originals``) and the private AI archive with SQLite metadata and Chroma
(``ai_archive``). The synthetic MCP index (``ai_demo``) is rebuilt from ``sample_docs`` and Ollama
weights are downloaded again, so neither is included.

The bundle is an uncompressed tar with ``manifest.json`` and three components. The manifest records
SHA-256 of every component, every file in both volumes, the row count and content hash of every
PostgreSQL table, and the applied migrations. ``restore`` refuses non-empty target volumes and then
compares the restored installation with that manifest, including SHA-256 of every original referenced
by ``documents``. With ``--passphrase-file`` each member is encrypted with GnuPG (AES-256) while it is
streamed, so plaintext archive data never lands in the backup directory.

The output contains only fixed messages, counts, table names and volume-relative file names; no
document titles or medical text are printed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Sequence

FORMAT = "local-medical-archive-backup"
FORMAT_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "manifest.json"
POSTGRES_COMPONENT = "postgres.dump"
VOLUMES = {"originals": "originals.tar.gz", "ai_archive": "ai_archive.tar.gz"}
VOLUME_KEYS = ("postgres_data", *VOLUMES)
WRITERS = ("gateway", "backend", "ai")
UPLOAD_ROOT = "/data/uploads/"
EXCLUDED = {
    "ai_demo": "synthetic MCP index; rebuilt from sample_docs on start",
    "ollama_models": "model weights; downloaded again by model-init",
}
GPG_SUFFIX = ".gpg"
CHUNK = 1024 * 1024

# One query: row count and an order-independent content hash of every table in schema public.
# The collation and time zone are fixed so the same data yields the same hash after pg_restore.
TABLE_QUERY = r"""
SELECT json_object_agg(t.table_name, json_build_object(
  'rows', (xpath('/row/c/text()', query_to_xml(format(
     'select count(*) as c from %I.%I', t.table_schema, t.table_name), false, true, '')))[1]::text::bigint,
  'sha256', (xpath('/row/h/text()', query_to_xml(format(
     'select encode(sha256(convert_to(coalesce(string_agg(x::text, E''\n'' order by x::text collate "C"), ''''),'
     ' ''UTF8'')), ''hex'') as h from %I.%I x', t.table_schema, t.table_name), false, true, '')))[1]::text
) ORDER BY t.table_name)
FROM information_schema.tables t
WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
"""
MIGRATION_QUERY = "SELECT coalesce(json_agg(name ORDER BY id), '[]'::json) FROM migrations"
ORIGINALS_QUERY = """
SELECT coalesce(json_agg(json_build_object('path', "storagePath", 'sha256', sha256) ORDER BY "storagePath"),
  '[]'::json) FROM documents WHERE "storagePath" IS NOT NULL
"""


class BackupError(RuntimeError):
    """A fixed, content-free failure message for the operator."""


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------------------------------
# Pure helpers: manifests and comparisons. These are unit tested without Docker.
# --------------------------------------------------------------------------------------------------

def parse_sha256sum(output: str) -> dict[str, str]:
    """Parse ``sha256sum`` lines for paths relative to a volume root (``./x`` becomes ``x``)."""
    files: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        if len(digest) != 64 or not name:
            raise BackupError("unexpected sha256sum output")
        files[name[2:] if name.startswith("./") else name] = digest
    return dict(sorted(files.items()))


def original_references(rows: list[dict], upload_root: str = UPLOAD_ROOT) -> dict[str, str | None]:
    """Map ``documents.storagePath`` to paths inside the originals volume."""
    references: dict[str, str | None] = {}
    for row in rows:
        path = row["path"]
        if not path.startswith(upload_root):
            raise BackupError("document storage path is outside the originals volume")
        references[path[len(upload_root):]] = row.get("sha256")
    return dict(sorted(references.items()))


def reference_issues(references: dict[str, str | None], files: dict[str, str]) -> list[dict]:
    """Originals referenced by the database that are missing or differ from ``documents.sha256``."""
    issues = []
    for path, expected in references.items():
        if path not in files:
            issues.append({"path": path, "problem": "missing"})
        elif expected and files[path] != expected:
            issues.append({"path": path, "problem": "sha256-mismatch"})
    return issues


def compare_files(label: str, expected: dict[str, str], actual: dict[str, str]) -> list[str]:
    problems = []
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(p for p in set(expected) & set(actual) if expected[p] != actual[p])
    for kind, paths in (("missing", missing), ("unexpected", extra), ("changed", changed)):
        if paths:
            problems.append(f"{label}: {len(paths)} {kind} file(s), first: {paths[0]}")
    return problems


def compare_database(expected: dict, actual: dict) -> list[str]:
    problems = []
    if expected["migrations"] != actual["migrations"]:
        problems.append("database: applied migrations differ")
    exp_tables, act_tables = expected["tables"], actual["tables"]
    for name in sorted(set(exp_tables) | set(act_tables)):
        if name not in act_tables:
            problems.append(f"database: table {name} is missing")
        elif name not in exp_tables:
            problems.append(f"database: unexpected table {name}")
        elif exp_tables[name]["rows"] != act_tables[name]["rows"]:
            problems.append(f"database: table {name} has {act_tables[name]['rows']} rows, "
                            f"expected {exp_tables[name]['rows']}")
        elif exp_tables[name]["sha256"] != act_tables[name]["sha256"]:
            problems.append(f"database: table {name} content differs")
    return problems


def verify_installation(manifest: dict, database: dict, volumes: dict[str, dict[str, str]],
                        references: dict[str, str | None]) -> list[str]:
    """Every difference between a restored installation and the manifest; empty means complete."""
    problems = compare_database(manifest["database"], database)
    for name in VOLUMES:
        problems += compare_files(name, manifest["volumes"][name]["files"], volumes[name])
    known = {(i["path"], i["problem"]) for i in manifest.get("sourceIssues", [])}
    for issue in reference_issues(references, volumes["originals"]):
        if (issue["path"], issue["problem"]) not in known:
            problems.append(f"originals: referenced file {issue['path']} is {issue['problem']}")
    return problems


def summary(manifest: dict) -> dict:
    tables = manifest["database"]["tables"]
    return {
        "createdAt": manifest["createdAt"],
        "encrypted": manifest["encrypted"],
        "tables": len(tables),
        "rows": sum(t["rows"] for t in tables.values()),
        "documents": tables.get("documents", {}).get("rows", 0),
        "migrations": len(manifest["database"]["migrations"]),
        "referencedOriginals": len(manifest["originals"]["referenced"]),
        "files": {name: len(manifest["volumes"][name]["files"]) for name in VOLUMES},
        "sourceIssues": len(manifest.get("sourceIssues", [])),
    }


# --------------------------------------------------------------------------------------------------
# Streams: hash plaintext while copying it, optionally through GnuPG.
# --------------------------------------------------------------------------------------------------

def gpg_command(passphrase_file: Path, decrypt: bool) -> list[str]:
    base = ["gpg", "--batch", "--quiet", "--no-tty", "--pinentry-mode", "loopback",
            "--passphrase-file", str(passphrase_file)]
    if decrypt:
        return base + ["--decrypt"]
    return base + ["--symmetric", "--cipher-algo", "AES256", "--s2k-mode", "3", "--s2k-digest-algo", "SHA512",
                   "--s2k-count", "65011712", "--compress-algo", "none"]


def copy_hashed(source: BinaryIO, sink: BinaryIO) -> dict:
    digest, size = hashlib.sha256(), 0
    while chunk := source.read(CHUNK):
        digest.update(chunk)
        size += len(chunk)
        sink.write(chunk)
    return {"sha256": digest.hexdigest(), "size": size}


def private_file(path: Path) -> BinaryIO:
    """Create a new file readable only by its owner: backups contain the whole medical archive."""
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")


def write_member(source: BinaryIO, path: Path, passphrase_file: Path | None) -> dict:
    """Write a stream to ``path`` (encrypted when a passphrase is given) and return plaintext hash/size."""
    if passphrase_file is None:
        with private_file(path) as out:
            return copy_hashed(source, out)
    with private_file(path) as out:
        gpg = subprocess.Popen(gpg_command(passphrase_file, False), stdin=subprocess.PIPE, stdout=out,
                               stderr=subprocess.DEVNULL)
        try:
            result = copy_hashed(source, gpg.stdin)
        finally:
            gpg.stdin.close()
        if gpg.wait() != 0:
            raise BackupError("encryption failed")
    return result


def read_member(path: Path, passphrase_file: Path | None, sink: BinaryIO) -> dict:
    """Stream a (possibly encrypted) member into ``sink`` and return plaintext hash/size."""
    if passphrase_file is None:
        with path.open("rb") as source:
            return copy_hashed(source, sink)
    gpg = subprocess.Popen(gpg_command(passphrase_file, True) + [str(path)], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL)
    result = copy_hashed(gpg.stdout, sink)
    if gpg.wait() != 0:
        raise BackupError("decryption failed: wrong passphrase or damaged backup")
    return result


class _Discard(io.RawIOBase):
    def writable(self) -> bool:
        return True

    def write(self, b) -> int:  # noqa: ANN001
        return len(b)


def member_name(name: str, encrypted: bool) -> str:
    return name + GPG_SUFFIX if encrypted else name


def pack(folder: Path, destination: Path, names: Sequence[str]) -> None:
    partial = destination.with_name(destination.name + ".partial")
    with private_file(partial) as raw, tarfile.open(fileobj=raw, mode="w") as bundle:
        for name in names:
            bundle.add(folder / name, arcname=name, recursive=False)
    partial.rename(destination)


def unpack(bundle_path: Path, folder: Path) -> list[str]:
    names = []
    with tarfile.open(bundle_path, "r") as bundle:
        for member in bundle.getmembers():
            if not member.isfile() or "/" in member.name or member.name.startswith("."):
                raise BackupError("unexpected member in backup bundle")
            if hasattr(tarfile, "data_filter"):
                bundle.extract(member, folder, filter="data")
            else:  # Python < 3.11.4; names were validated above.
                bundle.extract(member, folder)
            names.append(member.name)
    return names


def load_bundle(bundle_path: Path, folder: Path, passphrase_file: Path | None) -> dict:
    """Unpack a bundle, decrypt the manifest and check every component hash. Returns the manifest."""
    names = set(unpack(bundle_path, folder))
    encrypted = MANIFEST + GPG_SUFFIX in names
    if encrypted and passphrase_file is None:
        raise BackupError("backup is encrypted: pass --passphrase-file")
    if not encrypted and MANIFEST not in names:
        raise BackupError("backup has no manifest")
    buffer = io.BytesIO()
    read_member(folder / member_name(MANIFEST, encrypted), passphrase_file if encrypted else None, buffer)
    manifest = json.loads(buffer.getvalue())
    if manifest.get("format") != FORMAT or manifest.get("formatVersion") != FORMAT_VERSION:
        raise BackupError("unsupported backup format")
    if manifest["encrypted"] != encrypted:
        raise BackupError("backup encryption flag does not match its members")
    expected_names = {member_name(n, encrypted) for n in [MANIFEST, *manifest["components"]]}
    if names != expected_names:
        raise BackupError("backup members do not match the manifest")
    for name, expected in manifest["components"].items():
        actual = read_member(folder / member_name(name, encrypted), passphrase_file if encrypted else None,
                             _Discard())
        if actual != expected:
            raise BackupError(f"component {name} is damaged: hash or size differs from the manifest")
    return manifest


# --------------------------------------------------------------------------------------------------
# Docker Compose access.
# --------------------------------------------------------------------------------------------------

@dataclass
class Compose:
    files: Sequence[str]
    project: str | None
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run

    def base(self) -> list[str]:
        command = ["docker", "compose"]
        for file in self.files:
            command += ["-f", file]
        if self.project:
            command += ["-p", self.project]
        return command

    def run(self, args: Sequence[str], **kwargs) -> subprocess.CompletedProcess:
        return self.runner([*self.base(), *args], cwd=ROOT, check=True, **kwargs)

    def config(self) -> dict:
        output = self.run(["config", "--format", "json"], capture_output=True).stdout
        return json.loads(output)

    def running(self) -> list[str]:
        output = self.run(["ps", "--status", "running", "--services"], capture_output=True, text=True).stdout
        return [line for line in output.split() if line]

    def psql_json(self, query: str):
        output = self.run(["exec", "-T", "-e", "PGTZ=UTC", "postgres", "psql", "-X", "-q", "-A", "-t",
                           "-v", "ON_ERROR_STOP=1", "-U", "archive", "-d", "archive", "-c", query],
                          capture_output=True, text=True).stdout
        return json.loads(output.strip() or "null")


def volume_name(config: dict, key: str) -> str:
    return config["volumes"][key].get("name") or f"{config['name']}_{key}"


def docker(args: Sequence[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], check=True, **kwargs)


def volume_exists(name: str) -> bool:
    return subprocess.run(["docker", "volume", "inspect", name], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def tool_run(image: str, volume: str, script: str, read_only: bool = True, **kwargs):
    mount = f"{volume}:/v" + (":ro" if read_only else "")
    return docker(["run", "--rm", "-i", "--network", "none", "-v", mount, "--entrypoint", "sh", image,
                   "-c", script], **kwargs)


def volume_hashes(image: str, volume: str) -> dict[str, str]:
    output = tool_run(image, volume, "cd /v && find . -type f -print0 | xargs -0 -r sha256sum",
                      capture_output=True, text=True).stdout
    return parse_sha256sum(output)


def volume_is_empty(image: str, volume: str) -> bool:
    output = tool_run(image, volume, "find /v -mindepth 1 | head -n 1", capture_output=True, text=True).stdout
    return not output.strip()


def stream_process(command: Sequence[str], path: Path, passphrase_file: Path | None) -> dict:
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE)
    try:
        result = write_member(process.stdout, path, passphrase_file)
    finally:
        process.stdout.close()
    if process.wait() != 0:
        raise BackupError(f"export failed: {command[1]} exited with {process.returncode}")
    return result


def feed_process(command: Sequence[str], path: Path, passphrase_file: Path | None, expected: dict) -> None:
    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE)
    try:
        actual = read_member(path, passphrase_file, process.stdin)
    finally:
        process.stdin.close()
    if process.wait() != 0:
        raise BackupError(f"import failed: {command[1]} exited with {process.returncode}")
    if actual != expected:
        raise BackupError("component changed while it was restored")


def wait_postgres(compose: Compose, attempts: int = 90) -> None:
    # TCP is probed on purpose: the image's first-run init server listens only on the Unix socket and
    # then restarts, so a socket probe could accept a restore that the restart would interrupt.
    for _ in range(attempts):
        probe = compose.runner([*compose.base(), "exec", "-T", "postgres", "pg_isready", "-h", "127.0.0.1",
                                "-U", "archive", "-d", "archive"], cwd=ROOT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        if probe.returncode == 0:
            return
        time.sleep(2)
    raise BackupError("postgres did not become ready")


def inspect_installation(compose: Compose, image: str, config: dict) -> tuple[dict, dict, dict]:
    database = {"tables": compose.psql_json(TABLE_QUERY) or {}, "migrations": compose.psql_json(MIGRATION_QUERY)}
    volumes = {name: volume_hashes(image, volume_name(config, name)) for name in VOLUMES}
    references = original_references(compose.psql_json(ORIGINALS_QUERY))
    return database, volumes, references


def git_commit() -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def check_passphrase(path: Path | None) -> Path | None:
    if path is None:
        return None
    if not path.is_file() or not path.read_bytes().strip():
        raise BackupError("passphrase file is missing or empty")
    if shutil.which("gpg") is None:
        raise BackupError("gpg is required for encrypted backups")
    return path.resolve()


# --------------------------------------------------------------------------------------------------
# Commands.
# --------------------------------------------------------------------------------------------------

def backup(compose: Compose, output: Path, passphrase_file: Path | None) -> dict:
    config = compose.config()
    image = config["services"]["postgres"]["image"]
    for key in VOLUME_KEYS:
        if not volume_exists(volume_name(config, key)):
            raise BackupError(f"volume {key} does not exist for this Compose project")
    running = compose.running()
    if "postgres" not in running:
        raise BackupError("postgres is not running: start it with docker compose up -d postgres")
    stopped = [s for s in WRITERS if s in running]
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise BackupError("output file already exists")
    encrypted = passphrase_file is not None
    workdir = Path(tempfile.mkdtemp(prefix=".lma-backup-", dir=output.parent))
    try:
        if stopped:
            log(f"Stopping {', '.join(stopped)} for a consistent snapshot")
            compose.run(["stop", *stopped])
        wait_postgres(compose)
        log("Recording database and volume checksums")
        database, volumes, references = inspect_installation(compose, image, config)
        components = {}
        log("Exporting PostgreSQL")
        components[POSTGRES_COMPONENT] = stream_process(
            [*compose.base(), "exec", "-T", "postgres", "pg_dump", "-U", "archive", "-d", "archive", "-Fc",
             "--no-owner", "--no-privileges"], workdir / member_name(POSTGRES_COMPONENT, encrypted),
            passphrase_file)
        for name, component in VOLUMES.items():
            log(f"Exporting volume {name}")
            components[component] = stream_process(
                ["docker", "run", "--rm", "--network", "none", "-v", f"{volume_name(config, name)}:/v:ro",
                 "--entrypoint", "tar", image, "-C", "/v", "-czf", "-", "."],
                workdir / member_name(component, encrypted), passphrase_file)
        # Checksums taken after the export prove nothing changed while the writers were stopped.
        after_db, after_volumes, _ = inspect_installation(compose, image, config)
        if after_db != database or after_volumes != volumes:
            raise BackupError("archive changed during backup; nothing was written")
    finally:
        if stopped:
            log(f"Starting {', '.join(reversed(stopped))} again")
            compose.run(["up", "-d", "--no-build", "--no-recreate", *reversed(stopped)])
    try:
        issues = reference_issues(references, volumes["originals"])
        manifest = {
            "format": FORMAT, "formatVersion": FORMAT_VERSION,
            "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "encrypted": encrypted,
            "source": {"composeProject": config["name"], "gitCommit": git_commit(), "postgresImage": image},
            "components": components,
            "database": database,
            "volumes": {name: {"files": volumes[name]} for name in VOLUMES},
            "originals": {"referenced": references},
            "sourceIssues": issues,
            "excluded": EXCLUDED,
        }
        data = json.dumps(manifest, indent=2, sort_keys=True).encode()
        write_member(io.BytesIO(data), workdir / member_name(MANIFEST, encrypted), passphrase_file)
        pack(workdir, output, [member_name(n, encrypted) for n in [MANIFEST, *components]])
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    if issues:
        log(f"WARNING: {len(issues)} referenced original(s) were already missing or differ from documents.sha256 "
            "before backup; see sourceIssues in the manifest")
    return manifest


def verify(bundle: Path, passphrase_file: Path | None) -> dict:
    with tempfile.TemporaryDirectory(prefix=".lma-verify-", dir=bundle.parent) as folder:
        return load_bundle(bundle, Path(folder), passphrase_file)


def restore(compose: Compose, bundle: Path, passphrase_file: Path | None) -> dict:
    config = compose.config()
    image = config["services"]["postgres"]["image"]
    running = compose.running()
    if any(s in running for s in ("postgres", *WRITERS)):
        raise BackupError("target project is running; restore needs a stopped project with empty volumes")
    for key in VOLUME_KEYS:
        name = volume_name(config, key)
        if volume_exists(name) and not volume_is_empty(image, name):
            raise BackupError(f"volume {key} of the target project is not empty; use a new project name (-p) "
                              "or remove the old volumes deliberately")
    with tempfile.TemporaryDirectory(prefix=".lma-restore-", dir=bundle.parent) as tmp:
        folder = Path(tmp)
        log("Checking backup integrity")
        manifest = load_bundle(bundle, folder, passphrase_file)
        key = passphrase_file if manifest["encrypted"] else None
        encrypted = manifest["encrypted"]
        for name, component in VOLUMES.items():
            volume = volume_name(config, name)
            if not volume_exists(volume):
                docker(["volume", "create", "--label", f"com.docker.compose.project={config['name']}",
                        "--label", f"com.docker.compose.volume={name}", volume], stdout=subprocess.DEVNULL)
            log(f"Restoring volume {name}")
            feed_process(["docker", "run", "--rm", "-i", "--network", "none", "-v", f"{volume}:/v",
                          "--entrypoint", "tar", image, "-C", "/v", "-xzf", "-"],
                         folder / member_name(component, encrypted), key, manifest["components"][component])
        log("Starting postgres")
        compose.run(["up", "-d", "--no-build", "postgres"])
        wait_postgres(compose)
        log("Restoring PostgreSQL")
        feed_process([*compose.base(), "exec", "-T", "postgres", "pg_restore", "-U", "archive", "-d", "archive",
                      "--no-owner", "--no-privileges", "--exit-on-error", "--single-transaction"],
                     folder / member_name(POSTGRES_COMPONENT, encrypted), key,
                     manifest["components"][POSTGRES_COMPONENT])
    log("Verifying completeness against the manifest")
    problems = verify_installation(manifest, *inspect_installation(compose, image, config))
    if problems:
        for problem in problems:
            log(f"MISMATCH {problem}")
        raise BackupError(f"restore is incomplete: {len(problems)} difference(s) from the backup manifest")
    return manifest


def default_output() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "backups" / f"medical-archive-{stamp}.tar"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = root.add_subparsers(dest="command", required=True)

    def compose_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("-f", "--file", action="append", dest="files",
                       help="Compose file, repeatable; default compose.yaml")
        p.add_argument("-p", "--project-name", help="Compose project name; default from compose.yaml")

    b = sub.add_parser("backup", help="stop writers briefly and write a verified backup bundle")
    compose_args(b)
    b.add_argument("-o", "--output", type=Path, help="bundle path; default backups/medical-archive-<UTC>.tar")
    b.add_argument("--passphrase-file", type=Path, help="encrypt every member with GnuPG AES-256")
    v = sub.add_parser("verify", help="check a bundle's manifest and component hashes without restoring")
    v.add_argument("bundle", type=Path)
    v.add_argument("--passphrase-file", type=Path)
    r = sub.add_parser("restore", help="restore into empty volumes and verify completeness")
    compose_args(r)
    r.add_argument("bundle", type=Path)
    r.add_argument("--passphrase-file", type=Path)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        passphrase = check_passphrase(args.passphrase_file)
        if args.command == "verify":
            manifest = verify(args.bundle.resolve(), passphrase)
            label = "Backup is intact"
        else:
            compose = Compose(args.files or ["compose.yaml"], args.project_name)
            if args.command == "backup":
                output = (args.output or default_output()).resolve()
                manifest = backup(compose, output, passphrase)
                label = f"Backup written to {output}"
            else:
                manifest = restore(compose, args.bundle.resolve(), passphrase)
                label = "Restore complete and verified; start the stack with docker compose up -d"
    except BackupError as error:
        log(f"ERROR: {error}")
        return 1
    except subprocess.CalledProcessError as error:
        log(f"ERROR: command failed with exit code {error.returncode}: {' '.join(error.cmd[:3])}")
        return 1
    log(label)
    print(json.dumps(summary(manifest), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
