"""Release packaging contracts for the distributable server artifacts."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


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


def test_windows_release_sets_health_port_before_starting_server() -> None:
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
    health_index = verify_step.find("http://127.0.0.1:8765/api/health")
    assert min(port_index, start_index, health_index) >= 0
    assert port_index < start_index < health_index


@pytest.mark.skipif(os.name == "nt", reason="Linux bundle contract runs on POSIX")
def test_linux_bundle_copies_scripts_into_flat_import_path(tmp_path: Path) -> None:
    build_script = ROOT / "tools" / "server" / "build_linux.sh"
    copy_line = next(
        line.strip()
        for line in build_script.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith('cp -r "$TOOLS/scripts')
    )
    stage_root = tmp_path / "citeseal_server-linux-x64"
    (stage_root / "scripts").mkdir(parents=True)
    env = os.environ.copy()
    env.update({"TOOLS": str(ROOT / "tools"), "ROOT": str(stage_root)})

    subprocess.run(["bash", "-c", copy_line], env=env, check=True)

    assert (stage_root / "scripts" / "ci_common.py").is_file()
    assert not (stage_root / "scripts" / "scripts").exists()
