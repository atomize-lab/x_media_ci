"""Release packaging contracts for the distributable server artifacts."""
from __future__ import annotations

import importlib.util
import io
import re
import tarfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VERIFY_LINUX_TARBALL = ROOT / "tools" / "server" / "verify_linux_tarball.py"


def test_windows_release_installs_pyinstaller_before_build() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    windows_job = workflow.split("  windows-exe:", 1)[1].split(
        "  linux-tarball:", 1
    )[0]
    before_build, after_build = windows_job.split(
        "      - name: Build with PyInstaller", 1
    )

    assert re.search(
        r"python -m pip install(?:[^\n]*\s)?pyinstaller(?:[<>=!~].*)?$",
        before_build,
        flags=re.IGNORECASE | re.MULTILINE,
    ), "Windows release job must install PyInstaller before invoking it"
    assert "python -m PyInstaller" in after_build
    assert "--distpath tools/dist" in after_build


def test_windows_release_sets_port_before_starting_and_smoking_server() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    windows_job = workflow.split("  windows-exe:", 1)[1].split(
        "  linux-tarball:", 1
    )[0]
    verify_step = windows_job.split("      - name: Verify exe", 1)[1].split(
        "      - name: Upload artifact", 1
    )[0]

    port_index = verify_step.find('$env:CITESEAL_PORT = "8765"')
    start_index = verify_step.find("Start-Process")
    smoke_index = verify_step.find("smoke_test_server.py")
    assert min(port_index, start_index, smoke_index) >= 0
    assert port_index < start_index < smoke_index


def test_pyinstaller_spec_analyzes_embedded_cli_and_script_dependencies() -> None:
    spec = (ROOT / "tools" / "server" / "citeseal_server.spec").read_text(
        encoding="utf-8"
    )

    assert "script_modules" in spec
    assert "hiddenimports += script_modules" in spec
    assert "pathex=[str(server_dir), str(tools_root), str(scripts_pkg)]" in spec


def test_linux_bundle_builds_frozen_server_without_runtime_venv() -> None:
    script = (ROOT / "tools" / "server" / "build_linux.sh").read_text(
        encoding="utf-8"
    )

    assert 'if command -v uv' in script
    assert 'uv venv --seed --python python3 "$BUILD_VENV"' in script
    assert 'python3 -m venv "$BUILD_VENV"' in script
    assert '"$BUILD_VENV/bin/python" -m PyInstaller' in script
    assert '"$BUILD_DIST/citeseal_server"' in script
    assert '"$ROOT/bin/citeseal_server"' in script
    assert 'exec "$HERE/citeseal_server"' in script
    assert '"$ROOT/venv/bin/python"' not in script
    assert 'verify_linux_tarball.py" "$TARBALL"' in script


def test_release_workflow_verifies_linux_tarball_before_extracting() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    linux_job = workflow.split("  linux-tarball:", 1)[1].split(
        "  android-apk:", 1
    )[0]
    verifier_index = linux_job.find("verify_linux_tarball.py")
    extract_index = linux_job.find("tar -xzf")

    assert min(verifier_index, extract_index) >= 0
    assert verifier_index < extract_index


def test_release_workflow_smokes_background_jobs_without_host_python() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    windows_job = workflow.split("  windows-exe:", 1)[1].split(
        "  linux-tarball:", 1
    )[0]
    linux_job = workflow.split("  linux-tarball:", 1)[1].split(
        "  android-apk:", 1
    )[0]
    good_fixture = (
        "tests/fixtures/accounts/example_user/tweets/2026/2026-07/"
        "20260708_180000_1234567890"
    )

    assert "smoke_test_server.py" in windows_job
    assert "smoke_test_server.py" in linux_job
    assert good_fixture in windows_job
    assert good_fixture in linux_job
    assert 'CITESEAL_ROOT="$PWD/tests/fixtures/accounts"' not in linux_job
    assert '$env:PATH = "$env:SystemRoot\\System32"' in windows_job
    assert "PATH=/nonexistent" in linux_job
    assert "/bin/citeseal_server &" in linux_job


def _load_tarball_verifier():
    assert VERIFY_LINUX_TARBALL.is_file(), "Linux tarball verifier is required"
    spec = importlib.util.spec_from_file_location(
        "verify_linux_tarball", VERIFY_LINUX_TARBALL
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_tarball(
    path: Path,
    *,
    extra_member: tarfile.TarInfo | None = None,
    files: dict[str, bytes] | None = None,
    mode: int = 0o755,
) -> None:
    root = "citeseal_server-linux-x64"
    if files is None:
        files = {
            f"{root}/bin/citeseal_server": b"binary",
            f"{root}/bin/run.sh": b"#!/usr/bin/env bash\n",
        }
    with tarfile.open(path, "w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            archive.addfile(info, io.BytesIO(data))
        if extra_member is not None:
            archive.addfile(extra_member)


def test_linux_tarball_verifier_accepts_self_contained_layout(tmp_path: Path) -> None:
    verifier = _load_tarball_verifier()
    archive = tmp_path / "citeseal_server-linux-x64.tar.gz"
    _write_tarball(archive)

    summary = verifier.verify_tarball(archive)

    assert summary["members"] == 2
    assert summary["links"] == 0


@pytest.mark.parametrize(
    "bad_member",
    [
        tarfile.TarInfo("../../escape"),
        tarfile.TarInfo("/absolute/path"),
    ],
)
def test_linux_tarball_verifier_rejects_unsafe_paths(
    tmp_path: Path, bad_member: tarfile.TarInfo
) -> None:
    verifier = _load_tarball_verifier()
    archive = tmp_path / "citeseal_server-linux-x64.tar.gz"
    _write_tarball(archive, extra_member=bad_member)

    with pytest.raises(ValueError, match="unsafe path"):
        verifier.verify_tarball(archive)


def test_linux_tarball_verifier_rejects_links(tmp_path: Path) -> None:
    verifier = _load_tarball_verifier()
    archive = tmp_path / "citeseal_server-linux-x64.tar.gz"
    link = tarfile.TarInfo("citeseal_server-linux-x64/venv/bin/python3")
    link.type = tarfile.SYMTYPE
    link.linkname = "/opt/hostedtoolcache/Python/3.12/bin/python3"
    _write_tarball(archive, extra_member=link)

    with pytest.raises(ValueError, match="links are not allowed"):
        verifier.verify_tarball(archive)


def test_linux_tarball_verifier_rejects_duplicate_members(tmp_path: Path) -> None:
    verifier = _load_tarball_verifier()
    archive = tmp_path / "citeseal_server-linux-x64.tar.gz"
    duplicate = tarfile.TarInfo(
        "citeseal_server-linux-x64/bin/citeseal_server"
    )
    _write_tarball(archive, extra_member=duplicate)

    with pytest.raises(ValueError, match="duplicate tarball member"):
        verifier.verify_tarball(archive)


def test_linux_tarball_verifier_rejects_special_files(tmp_path: Path) -> None:
    verifier = _load_tarball_verifier()
    archive = tmp_path / "citeseal_server-linux-x64.tar.gz"
    device = tarfile.TarInfo("citeseal_server-linux-x64/bin/device")
    device.type = tarfile.CHRTYPE
    _write_tarball(archive, extra_member=device)

    with pytest.raises(ValueError, match="special file is not allowed"):
        verifier.verify_tarball(archive)


def test_linux_tarball_verifier_requires_all_launchers(tmp_path: Path) -> None:
    verifier = _load_tarball_verifier()
    archive = tmp_path / "citeseal_server-linux-x64.tar.gz"
    root = "citeseal_server-linux-x64"
    _write_tarball(
        archive,
        files={f"{root}/bin/run.sh": b"#!/usr/bin/env bash\n"},
    )

    with pytest.raises(ValueError, match="required release files missing"):
        verifier.verify_tarball(archive)


def test_linux_tarball_verifier_requires_executable_launchers(
    tmp_path: Path,
) -> None:
    verifier = _load_tarball_verifier()
    archive = tmp_path / "citeseal_server-linux-x64.tar.gz"
    _write_tarball(archive, mode=0o644)

    with pytest.raises(ValueError, match="release files are not executable"):
        verifier.verify_tarball(archive)
