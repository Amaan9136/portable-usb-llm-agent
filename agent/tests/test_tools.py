"""Unit tests for tools.py, focused on the security containment
guarantees. These tests intentionally try to break out of the
workspace/artifacts sandbox in the same ways an adversarial or
hallucinating model might."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import config
import tools


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    """Point WORKSPACE/ARTIFACTS at a throwaway tmp_path for every test
    so tests never touch the real project workspace/artifacts."""
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir()
    artifacts.mkdir()

    monkeypatch.setattr(tools, "WORKSPACE", workspace)
    monkeypatch.setattr(tools, "ARTIFACTS", artifacts)
    monkeypatch.setattr(config, "WORKSPACE", workspace)
    monkeypatch.setattr(config, "ARTIFACTS", artifacts)

    yield workspace, artifacts


# --- Path traversal ------------------------------------------------

def test_rejects_dotdot_traversal(isolated_dirs):
    result = tools.read_file("../outside.txt")
    assert result["ok"] is False
    assert "escapes" in result["error"] or "traversal" in result["error"].lower()


def test_rejects_nested_dotdot_traversal(isolated_dirs):
    result = tools.write_file("subdir/../../escape.txt", "x")
    assert result["ok"] is False


def test_rejects_absolute_posix_path(isolated_dirs):
    result = tools.read_file("/etc/passwd")
    assert result["ok"] is False
    assert "absolute" in result["error"].lower()


def test_rejects_absolute_windows_path(isolated_dirs):
    result = tools.read_file("C:\\Windows\\System32\\config\\SAM")
    assert result["ok"] is False


def test_rejects_drive_relative_path(isolated_dirs):
    result = tools.read_file("C:foo\\bar.txt")
    assert result["ok"] is False


def test_rejects_unc_path(isolated_dirs):
    result = tools.read_file("\\\\server\\share\\file.txt")
    assert result["ok"] is False


def test_rejects_reserved_device_name(isolated_dirs):
    result = tools.write_file("CON.txt", "x")
    assert result["ok"] is False
    assert "reserved" in result["error"].lower()


def test_allows_plain_relative_path(isolated_dirs):
    workspace, _ = isolated_dirs
    result = tools.write_file("hello.py", "print('hi')")
    assert result["ok"] is True
    assert (workspace / "hello.py").is_file()


def test_allows_nested_relative_path(isolated_dirs):
    result = tools.write_file("pkg/module.py", "x = 1")
    assert result["ok"] is True


def test_symlink_escape_is_blocked(isolated_dirs):
    workspace, _ = isolated_dirs
    outside = workspace.parent / "secret.txt"
    outside.write_text("top secret")

    link = workspace / "link_out"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not supported on this filesystem/OS")

    result = tools.read_file("link_out")
    assert result["ok"] is False


# --- write_file overwrite protection ---------------------------------

def test_write_file_refuses_overwrite_by_default(isolated_dirs):
    tools.write_file("existing.txt", "v1")
    result = tools.write_file("existing.txt", "v2")
    assert result["ok"] is False
    assert "overwrite" in result["error"].lower()


def test_write_file_allows_overwrite_when_flagged(isolated_dirs):
    tools.write_file("existing.txt", "v1")
    result = tools.write_file("existing.txt", "v2", allow_overwrite=True)
    assert result["ok"] is True


# --- run_command allowlist / gating -----------------------------------

def test_run_command_blocked_without_allow_commands(isolated_dirs):
    result = tools.run_command(["python", "--version"], allow_commands=False)
    assert result["ok"] is False
    assert "allow_commands" in result["error"]


def test_run_command_rejects_disallowed_executable(isolated_dirs):
    result = tools.run_command(["curl", "http://example.com"], allow_commands=True)
    assert result["ok"] is False
    assert "curl" in result["error"]


def test_run_command_rejects_powershell(isolated_dirs):
    result = tools.run_command(["powershell", "-c", "whoami"], allow_commands=True)
    assert result["ok"] is False


def test_run_command_rejects_rm(isolated_dirs):
    result = tools.run_command(["rm", "-rf", "."], allow_commands=True)
    assert result["ok"] is False


def test_run_command_allows_python_version(isolated_dirs):
    result = tools.run_command(["python", "--version"], allow_commands=True)
    # ok reflects the command's own exit code; here we only assert it was
    # actually permitted to run (no allowlist/permission error).
    assert "error" not in result or "Allowed:" not in result.get("error", "")


def test_run_command_never_uses_shell(monkeypatch, isolated_dirs):
    captured = {}

    def fake_run(command, cwd, text, capture_output, timeout, shell):
        captured["shell"] = shell
        captured["command"] = command

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    monkeypatch.setattr(tools.subprocess, "run", fake_run)
    tools.run_command(["python", "--version"], allow_commands=True)
    assert captured["shell"] is False


def test_run_command_timeout(monkeypatch, isolated_dirs):
    import subprocess as sp

    def fake_run(*args, **kwargs):
        raise sp.TimeoutExpired(cmd="python", timeout=1)

    monkeypatch.setattr(tools.subprocess, "run", fake_run)
    result = tools.run_command(["python", "-c", "import time; time.sleep(999)"], allow_commands=True)
    assert result["ok"] is False
    assert "timeout" in result["error"].lower()


def test_run_command_rejects_bad_cwd(isolated_dirs):
    result = tools.run_command(["python", "--version"], relative_cwd="../../etc", allow_commands=True)
    assert result["ok"] is False


# --- create_zip ---------------------------------------------------

def test_create_zip_success(isolated_dirs):
    workspace, artifacts = isolated_dirs
    (workspace / "proj").mkdir()
    (workspace / "proj" / "main.py").write_text("print('hi')")

    result = tools.create_zip("proj", "myproject")
    assert result["ok"] is True
    assert result["artifact"] == "myproject.zip"
    assert (artifacts / "myproject.zip").is_file()


def test_create_zip_appends_extension(isolated_dirs):
    workspace, _ = isolated_dirs
    (workspace / "f.txt").write_text("x")
    result = tools.create_zip("f.txt", "no_extension_name")
    assert result["artifact"].endswith(".zip")


def test_create_zip_rejects_posix_traversal_in_name(isolated_dirs):
    workspace, _ = isolated_dirs
    (workspace / "f.txt").write_text("x")
    result = tools.create_zip("f.txt", "../../evil")
    assert result["ok"] is False


def test_create_zip_rejects_windows_backslash_traversal_in_name(isolated_dirs):
    # This is the case that matters most since the deployed target is
    # Windows: PureWindowsPath must be used to parse artifact_name, not
    # a platform-default Path, or "..\\..\\evil" slips through as an
    # opaque "filename" on a POSIX test host.
    workspace, _ = isolated_dirs
    (workspace / "f.txt").write_text("x")
    result = tools.create_zip("f.txt", "..\\..\\evil")
    assert result["ok"] is False


def test_create_zip_rejects_nested_subdir_in_name(isolated_dirs):
    workspace, _ = isolated_dirs
    (workspace / "f.txt").write_text("x")
    result = tools.create_zip("f.txt", "subdir/evil")
    assert result["ok"] is False


def test_create_zip_rejects_absolute_name(isolated_dirs):
    workspace, _ = isolated_dirs
    (workspace / "f.txt").write_text("x")
    result = tools.create_zip("f.txt", "C:\\evil.zip")
    assert result["ok"] is False


def test_create_zip_rejects_missing_source(isolated_dirs):
    result = tools.create_zip("does_not_exist", "out")
    assert result["ok"] is False


# --- delete_path is permanently disabled ------------------------------

def test_delete_path_always_disabled(isolated_dirs):
    result = tools.delete_path("anything.txt")
    assert result["ok"] is False
    assert "disabled" in result["error"].lower()


# --- safe_artifact_path (used by the download endpoint) ---------------

def test_safe_artifact_path_rejects_separators(isolated_dirs):
    with pytest.raises(tools.PathSecurityError):
        tools.safe_artifact_path("../secret.zip")

    with pytest.raises(tools.PathSecurityError):
        tools.safe_artifact_path("sub/dir.zip")


def test_safe_artifact_path_rejects_non_zip(isolated_dirs):
    with pytest.raises(tools.PathSecurityError):
        tools.safe_artifact_path("notes.txt")


def test_safe_artifact_path_rejects_missing_file(isolated_dirs):
    with pytest.raises(FileNotFoundError):
        tools.safe_artifact_path("does_not_exist.zip")


def test_safe_artifact_path_allows_valid_zip(isolated_dirs):
    _, artifacts = isolated_dirs
    (artifacts / "real.zip").write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # minimal empty zip
    path = tools.safe_artifact_path("real.zip")
    assert path.name == "real.zip"