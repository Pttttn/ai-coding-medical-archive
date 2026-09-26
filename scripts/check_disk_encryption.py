"""Check that the disk holding Docker data of the personal archive is encrypted at rest.

Diagnoses, documents and originals sit in plain form in the PostgreSQL, originals and AI volumes; the
application does not encrypt fields, because that would break search. Protection against a stolen or
discarded disk is full-disk encryption on the host, which a container cannot see. Run this on the host
before the first start of the personal mode and after moving Docker data.

Linux: the block device under Docker's data root must have a dm-crypt (LUKS) layer, or the ZFS dataset
must have encryption enabled. macOS: FileVault. Windows: BitLocker on the drive with Docker Desktop's
data. Docker Desktop on any OS keeps volumes in a VM disk inside the user's profile, so that location
is checked instead of the path inside the VM.

Exit codes: 0 encrypted, 1 not encrypted, 2 could not be determined. Output is a fixed message and the
checked path, never archive content.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Callable, Sequence

ENCRYPTED, NOT_ENCRYPTED, UNKNOWN = "ENCRYPTED", "NOT_ENCRYPTED", "UNKNOWN"
EXIT = {ENCRYPTED: 0, NOT_ENCRYPTED: 1, UNKNOWN: 2}
Runner = Callable[[Sequence[str]], "str | None"]


@dataclass(frozen=True)
class Result:
    status: str
    detail: str


def run_command(args: Sequence[str]) -> str | None:
    """Output of a command, or None when it is missing, fails or times out."""
    try:
        done = subprocess.run(list(args), capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def docker_location(run: Runner) -> tuple[str | None, bool]:
    """Docker data root and whether it lives inside a Docker Desktop VM."""
    info = run(["docker", "info", "--format", "{{.DockerRootDir}}|{{.OperatingSystem}}"])
    if not info or "|" not in info:
        return None, False
    root, system = info.strip().split("|", 1)
    return root or None, "Docker Desktop" in system


def linux_status(path: str, run: Runner) -> Result:
    # findmnt --target needs an existing path; a data root not created yet lives on its parent's device.
    target = Path(path)
    while not target.exists() and target != target.parent:
        target = target.parent
    source = run(["findmnt", "-no", "SOURCE,FSTYPE", "--target", str(target)])
    if not source or not source.split():
        return Result(UNKNOWN, f"не удалось определить устройство для {path}")
    device, fstype = (source.split() + [""])[:2]
    if fstype == "zfs":
        encryption = run(["zfs", "get", "-H", "-o", "value", "encryption", device])
        if encryption is None:
            return Result(UNKNOWN, f"не удалось прочитать шифрование ZFS для {path}")
        if encryption.strip() not in {"", "off", "-"}:
            return Result(ENCRYPTED, f"{path}: ZFS с шифрованием")
        return Result(NOT_ENCRYPTED, f"{path}: ZFS без шифрования")
    device = device.split("[", 1)[0]
    if not device.startswith("/dev/"):
        return Result(UNKNOWN, f"{path}: файловая система {fstype or 'без устройства'}, шифрование не определяется")
    layers = run(["lsblk", "-snlo", "TYPE", device])
    if layers is None:
        return Result(UNKNOWN, f"не удалось прочитать слои устройства для {path}")
    if "crypt" in layers.split():
        return Result(ENCRYPTED, f"{path}: устройство с dm-crypt/LUKS")
    return Result(NOT_ENCRYPTED, f"{path}: устройство без dm-crypt/LUKS")


def macos_status(path: str, run: Runner) -> Result:
    # Docker data and the user profile are on the system data volume, which FileVault protects.
    status = run(["fdesetup", "status"])
    if status is None:
        return Result(UNKNOWN, "не удалось выполнить fdesetup status")
    if "FileVault is On" in status:
        return Result(ENCRYPTED, f"{path}: FileVault включён")
    if "FileVault is Off" in status:
        return Result(NOT_ENCRYPTED, f"{path}: FileVault выключен")
    return Result(UNKNOWN, "FileVault в процессе включения или выключения")


def windows_status(path: str, run: Runner) -> Result:
    drive = PureWindowsPath(path).drive or "C:"
    # Enum names of ProtectionStatus are not localised, unlike manage-bde output. Reading it needs admin rights.
    status = run(["powershell", "-NoProfile", "-Command", f"(Get-BitLockerVolume -MountPoint '{drive}').ProtectionStatus"])
    if status is None:
        return Result(UNKNOWN, f"не удалось прочитать BitLocker для {drive}; запустите от имени администратора")
    value = status.strip()
    if value == "On":
        return Result(ENCRYPTED, f"{drive}: BitLocker включён")
    if value == "Off":
        return Result(NOT_ENCRYPTED, f"{drive}: BitLocker выключен")
    return Result(UNKNOWN, f"{drive}: состояние BitLocker не определено")


def desktop_data_path(system: str, home: Path) -> str:
    if system == "Darwin":
        return str(home / "Library" / "Containers" / "com.docker.docker")
    if system == "Windows":
        return os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")) + "\\Docker"
    return str(home / ".docker" / "desktop")


def check(system: str | None = None, run: Runner = run_command, home: Path | None = None) -> Result:
    system = system or platform.system()
    home = home or Path.home()
    root, desktop = docker_location(run)
    if root is None and system == "Linux":
        # Docker is not running: assume the native engine's default data root.
        root = "/var/lib/docker"
    path = desktop_data_path(system, home) if desktop or root is None else root
    if system == "Darwin":
        return macos_status(path, run)
    if system == "Windows":
        return windows_status(path, run)
    if system == "Linux":
        return linux_status(path, run)
    return Result(UNKNOWN, f"проверка для {system} не поддерживается")


MESSAGES = {
    ENCRYPTED: "Диск с данными Docker зашифрован.",
    NOT_ENCRYPTED: "Диск с данными Docker НЕ зашифрован: включите шифрование диска до загрузки личных документов.",
    UNKNOWN: "Не удалось определить шифрование диска с данными Docker: проверьте его вручную.",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    result = check()
    print(MESSAGES[result.status])
    print(result.detail)
    if result.status != ENCRYPTED:
        print("Инструкция: README, раздел «Шифрование данных на диске».")
    return EXIT[result.status]


if __name__ == "__main__":
    sys.exit(main())
