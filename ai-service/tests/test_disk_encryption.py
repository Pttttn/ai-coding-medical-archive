"""Host disk encryption check for the personal archive (review finding 9). Commands are simulated."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import check_disk_encryption as cde  # noqa: E402


def runner(outputs):
    calls = []

    def run(args):
        calls.append(list(args))
        for prefix, output in outputs.items():
            if tuple(args[:len(prefix)]) == prefix:
                return output
        return None
    run.calls = calls
    return run


def assert_target(run, path):
    # findmnt is given the path itself or, when it does not exist yet, its nearest existing parent.
    target = next(call[-1] for call in run.calls if call[0] == "findmnt")
    assert path == target or path.startswith(target.rstrip("/") + "/")


DOCKER_LINUX = {("docker", "info"): "/var/lib/docker|Ubuntu 24.04 LTS\n"}


@pytest.mark.parametrize("layers,status", [("part\ncrypt\ndisk\n", cde.ENCRYPTED), ("part\ndisk\n", cde.NOT_ENCRYPTED)])
def test_linux_luks_layer_decides(layers, status):
    run = runner({**DOCKER_LINUX, ("findmnt",): "/dev/mapper/root ext4\n", ("lsblk",): layers})
    result = cde.check("Linux", run, Path("/home/u"))
    assert result.status == status
    assert_target(run, "/var/lib/docker")


def test_linux_btrfs_subvolume_device_is_resolved():
    run = runner({**DOCKER_LINUX, ("findmnt",): "/dev/nvme0n1p3[/@docker] btrfs\n", ("lsblk",): "crypt\npart\ndisk\n"})
    assert cde.check("Linux", run, Path("/home/u")).status == cde.ENCRYPTED
    assert ["lsblk", "-snlo", "TYPE", "/dev/nvme0n1p3"] in run.calls


@pytest.mark.parametrize("value,status", [("aes-256-gcm\n", cde.ENCRYPTED), ("off\n", cde.NOT_ENCRYPTED)])
def test_linux_zfs_native_encryption(value, status):
    run = runner({**DOCKER_LINUX, ("findmnt",): "tank/docker zfs\n", ("zfs",): value})
    assert cde.check("Linux", run, Path("/home/u")).status == status


def test_linux_without_block_device_or_tools_is_unknown():
    assert cde.check("Linux", runner({**DOCKER_LINUX, ("findmnt",): "overlay overlay\n"}), Path("/h")).status == cde.UNKNOWN
    assert cde.check("Linux", runner(DOCKER_LINUX), Path("/h")).status == cde.UNKNOWN


def test_docker_desktop_on_linux_checks_the_vm_disk_in_home():
    run = runner({("docker", "info"): "/var/lib/docker|Docker Desktop\n", ("findmnt",): "/dev/sda2 ext4\n", ("lsblk",): "part\ndisk\n"})
    assert cde.check("Linux", run, Path("/home/u")).status == cde.NOT_ENCRYPTED
    assert_target(run, "/home/u/.docker/desktop")


@pytest.mark.parametrize("output,status", [("FileVault is On.\n", cde.ENCRYPTED), ("FileVault is Off.\n", cde.NOT_ENCRYPTED),
                                           ("Encryption in progress\n", cde.UNKNOWN), (None, cde.UNKNOWN)])
def test_macos_filevault(output, status):
    run = runner({("docker", "info"): "/var/lib/docker|Docker Desktop\n", ("fdesetup",): output})
    assert cde.check("Darwin", run, Path("/Users/u")).status == status


@pytest.mark.parametrize("output,status", [("On\r\n", cde.ENCRYPTED), ("Off\r\n", cde.NOT_ENCRYPTED), (None, cde.UNKNOWN)])
def test_windows_bitlocker_uses_unlocalised_status(output, status, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", "D:\\Users\\u\\AppData\\Local")
    run = runner({("docker", "info"): "/var/lib/docker|Docker Desktop\n", ("powershell",): output})
    assert cde.check("Windows", run, Path("D:/Users/u")).status == status
    powershell = next(call for call in run.calls if call[0] == "powershell")
    assert "-MountPoint 'D:'" in powershell[-1]


def test_docker_not_running_falls_back_to_desktop_location():
    run = runner({("fdesetup",): "FileVault is On.\n"})
    assert cde.check("Darwin", run, Path("/Users/u")).status == cde.ENCRYPTED


def test_exit_code_and_fixed_output(monkeypatch, capsys):
    monkeypatch.setattr(cde, "check", lambda: cde.Result(cde.NOT_ENCRYPTED, "/var/lib/docker: устройство без dm-crypt/LUKS"))
    assert cde.main([]) == 1
    output = capsys.readouterr().out
    assert "НЕ зашифрован" in output and "README" in output
