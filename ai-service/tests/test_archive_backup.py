"""Backup bundle and completeness checks. Docker itself is exercised by the manual Compose run in README."""
import copy
import io
import json
import shutil
import stat
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import archive_backup as ab  # noqa: E402

DIGEST = {name: ch * 64 for name, ch in (("a", "a"), ("b", "b"), ("c", "c"))}


def manifest_for(components, encrypted=False):
    return {
        "format": ab.FORMAT, "formatVersion": ab.FORMAT_VERSION, "createdAt": "2026-09-25T00:00:00Z",
        "encrypted": encrypted, "components": components,
        "database": {"migrations": ["Initial1750000000000"],
                     "tables": {"documents": {"rows": 2, "sha256": DIGEST["a"]},
                                "migrations": {"rows": 1, "sha256": DIGEST["b"]}}},
        "volumes": {"originals": {"files": {"one.pdf": DIGEST["a"], "two.txt": DIGEST["b"]}},
                    "ai_archive": {"files": {"archive/metadata.sqlite3": DIGEST["c"]}}},
        "originals": {"referenced": {"one.pdf": DIGEST["a"], "two.txt": DIGEST["b"]}},
        "sourceIssues": [],
    }


def installation(manifest):
    return (copy.deepcopy(manifest["database"]),
            {name: dict(manifest["volumes"][name]["files"]) for name in ab.VOLUMES},
            dict(manifest["originals"]["referenced"]))


def make_bundle(tmp_path, passphrase=None, payloads=None):
    payloads = payloads or {ab.POSTGRES_COMPONENT: b"synthetic dump", "originals.tar.gz": b"synthetic originals",
                            "ai_archive.tar.gz": b"synthetic index"}
    work = tmp_path / "work"
    work.mkdir()
    encrypted = passphrase is not None
    components = {name: ab.write_member(io.BytesIO(data), work / ab.member_name(name, encrypted), passphrase)
                  for name, data in payloads.items()}
    manifest = manifest_for(components, encrypted)
    ab.write_member(io.BytesIO(json.dumps(manifest).encode()), work / ab.member_name(ab.MANIFEST, encrypted),
                    passphrase)
    bundle = tmp_path / "backup.tar"
    ab.pack(work, bundle, [ab.member_name(n, encrypted) for n in [ab.MANIFEST, *components]])
    return bundle, manifest, work


def test_sha256sum_output_is_relative_to_volume_root():
    output = f"{DIGEST['a']}  ./archive/chroma/x.bin\n{DIGEST['b']}  ./one.pdf\n"
    assert ab.parse_sha256sum(output) == {"archive/chroma/x.bin": DIGEST["a"], "one.pdf": DIGEST["b"]}
    with pytest.raises(ab.BackupError):
        ab.parse_sha256sum("not a checksum line")


def test_document_paths_must_live_in_the_originals_volume():
    rows = [{"path": "/data/uploads/one.pdf", "sha256": DIGEST["a"]}]
    assert ab.original_references(rows) == {"one.pdf": DIGEST["a"]}
    with pytest.raises(ab.BackupError):
        ab.original_references([{"path": "/etc/passwd", "sha256": None}])


def test_identical_installation_is_complete():
    manifest = manifest_for({})
    assert ab.verify_installation(manifest, *installation(manifest)) == []


@pytest.mark.parametrize("mutate, expected", [
    (lambda db, vol, ref: vol["originals"].pop("two.txt"), "originals: 1 missing"),
    (lambda db, vol, ref: vol["originals"].update({"one.pdf": DIGEST["c"]}), "originals: 1 changed"),
    (lambda db, vol, ref: vol["ai_archive"].update({"stray": DIGEST["a"]}), "ai_archive: 1 unexpected"),
    (lambda db, vol, ref: db["tables"]["documents"].update(rows=1), "documents has 1 rows, expected 2"),
    (lambda db, vol, ref: db["tables"]["documents"].update(sha256=DIGEST["c"]), "documents content differs"),
    (lambda db, vol, ref: db["tables"].pop("migrations"), "table migrations is missing"),
    (lambda db, vol, ref: db["migrations"].append("Later1"), "applied migrations differ"),
    (lambda db, vol, ref: ref.update({"one.pdf": DIGEST["b"]}), "one.pdf is sha256-mismatch"),
])
def test_every_kind_of_incomplete_restore_is_reported(mutate, expected):
    manifest = manifest_for({})
    database, volumes, references = installation(manifest)
    mutate(database, volumes, references)
    problems = ab.verify_installation(manifest, database, volumes, references)
    assert any(expected in problem for problem in problems), problems


def test_problems_present_before_backup_are_reported_once_not_as_restore_failures():
    manifest = manifest_for({})
    manifest["volumes"]["originals"]["files"].pop("two.txt")
    manifest["sourceIssues"] = ab.reference_issues(manifest["originals"]["referenced"],
                                                   manifest["volumes"]["originals"]["files"])
    assert manifest["sourceIssues"] == [{"path": "two.txt", "problem": "missing"}]
    assert ab.verify_installation(manifest, *installation(manifest)) == []
    assert ab.summary(manifest)["sourceIssues"] == 1


def test_plain_bundle_round_trip_and_owner_only_permissions(tmp_path):
    bundle, manifest, _ = make_bundle(tmp_path)
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o600
    target = tmp_path / "check"
    target.mkdir()
    assert ab.load_bundle(bundle, target, None) == manifest


def test_damaged_component_is_rejected(tmp_path):
    bundle, _, work = make_bundle(tmp_path)
    (work / "originals.tar.gz").chmod(0o600)
    (work / "originals.tar.gz").write_bytes(b"synthetic originalZ")
    bundle.unlink()
    ab.pack(work, bundle, [ab.MANIFEST, ab.POSTGRES_COMPONENT, "originals.tar.gz", "ai_archive.tar.gz"])
    target = tmp_path / "check"
    target.mkdir()
    with pytest.raises(ab.BackupError, match="originals.tar.gz is damaged"):
        ab.load_bundle(bundle, target, None)


def test_members_outside_the_bundle_root_or_missing_are_rejected(tmp_path):
    evil = tmp_path / "evil.tar"
    with tarfile.open(evil, "w") as archive:
        info = tarfile.TarInfo("../manifest.json")
        info.size = 2
        archive.addfile(info, io.BytesIO(b"{}"))
    (tmp_path / "a").mkdir()
    with pytest.raises(ab.BackupError, match="unexpected member"):
        ab.load_bundle(evil, tmp_path / "a", None)

    bundle, _, work = make_bundle(tmp_path)
    bundle.unlink()
    ab.pack(work, bundle, [ab.MANIFEST, ab.POSTGRES_COMPONENT, "originals.tar.gz"])
    (tmp_path / "b").mkdir()
    with pytest.raises(ab.BackupError, match="do not match the manifest"):
        ab.load_bundle(bundle, tmp_path / "b", None)


@pytest.fixture
def passphrase(tmp_path, monkeypatch):
    if shutil.which("gpg") is None:
        pytest.skip("gpg is not installed")
    home = tmp_path / "gnupg"
    home.mkdir(mode=0o700)
    monkeypatch.setenv("GNUPGHOME", str(home))
    path = tmp_path / "passphrase"
    path.write_text("synthetic-test-passphrase\n")
    return path


def test_encrypted_bundle_hides_content_and_needs_the_passphrase(tmp_path, passphrase):
    secret = b"SYNTHETIC-MARKER hemoglobin 131 g/L"
    bundle, manifest, _ = make_bundle(tmp_path, passphrase, {
        ab.POSTGRES_COMPONENT: secret, "originals.tar.gz": b"o", "ai_archive.tar.gz": b"i"})
    raw = bundle.read_bytes()
    assert b"SYNTHETIC-MARKER" not in raw and b"hemoglobin" not in raw
    assert b"one.pdf" not in raw  # the manifest is encrypted too
    (tmp_path / "ok").mkdir()
    assert ab.load_bundle(bundle, tmp_path / "ok", passphrase) == manifest

    (tmp_path / "nokey").mkdir()
    with pytest.raises(ab.BackupError, match="pass --passphrase-file"):
        ab.load_bundle(bundle, tmp_path / "nokey", None)
    wrong = tmp_path / "wrong"
    wrong.write_text("another synthetic passphrase\n")
    (tmp_path / "wrongkey").mkdir()
    with pytest.raises(ab.BackupError, match="wrong passphrase"):
        ab.load_bundle(bundle, tmp_path / "wrongkey", wrong)


def test_compose_arguments_and_volume_names():
    compose = ab.Compose(["compose.yaml", "compose.personal.yaml"], "medical-personal")
    assert compose.base() == ["docker", "compose", "-f", "compose.yaml", "-f", "compose.personal.yaml",
                              "-p", "medical-personal"]
    config = {"name": "medical-personal", "volumes": {"originals": {}, "ai_archive": {"name": "custom"}}}
    assert ab.volume_name(config, "originals") == "medical-personal_originals"
    assert ab.volume_name(config, "ai_archive") == "custom"


def test_empty_passphrase_file_is_refused(tmp_path):
    empty = tmp_path / "empty"
    empty.write_text("\n")
    with pytest.raises(ab.BackupError, match="missing or empty"):
        ab.check_passphrase(empty)
