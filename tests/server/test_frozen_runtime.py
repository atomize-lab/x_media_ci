"""Contracts for the self-contained PyInstaller server runtime."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS_DIR = ROOT / "tools"
SCRIPTS_DIR = TOOLS_DIR / "scripts"
SERVER_DIR = TOOLS_DIR / "server"
for _path in (str(SCRIPTS_DIR), str(TOOLS_DIR), str(SERVER_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

frozen_entry = importlib.import_module("_frozen_entry")
server_app = importlib.import_module("app")
cli = importlib.import_module("citeseal")


def test_frozen_server_job_reexecutes_itself_in_cli_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server_app, "FROZEN", True, raising=False)
    monkeypatch.setattr(server_app, "PYTHON", "/bundle/citeseal_server")
    job = server_app.Job(
        id="job1",
        op="validate",
        args={"root": "/data/accounts", "quiet": True},
    )

    assert server_app._job_command(job) == [
        "/bundle/citeseal_server",
        "--citeseal-cli",
        "validate",
        "--root",
        "/data/accounts",
        "--quiet",
    ]


def test_frozen_entry_dispatches_embedded_cli_before_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert hasattr(frozen_entry, "_run_embedded_cli")
    assert hasattr(frozen_entry, "_run_server")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        frozen_entry,
        "_run_embedded_cli",
        lambda argv: calls.append(list(argv)) or 7,
    )
    monkeypatch.setattr(
        frozen_entry,
        "_run_server",
        lambda: pytest.fail("server must not start in embedded CLI mode"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["citeseal_server", "--citeseal-cli", "doctor"],
    )

    assert frozen_entry.main() == 7
    assert calls == [["doctor"]]


def test_frozen_cli_runs_bundled_script_in_process_and_restores_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    workdir = tmp_path / "work"
    workdir.mkdir()
    probe = scripts / "probe.py"
    probe.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path('probe.json').write_text(json.dumps({\n"
        "    'argv': sys.argv, 'cwd': os.getcwd(), 'name': __name__\n"
        "}), encoding='utf-8')\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )

    original_cwd = Path.cwd()
    original_argv = list(sys.argv)
    monkeypatch.setattr(cli, "_SCRIPTS_DIR", scripts)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail(
            "frozen CLI must not require a host Python subprocess"
        ),
    )

    assert cli._run_script("probe.py", ["alpha", "beta"], cwd=workdir) == 7

    result = json.loads((workdir / "probe.json").read_text(encoding="utf-8"))
    assert result["argv"] == [str(probe), "alpha", "beta"]
    assert result["cwd"] == str(workdir)
    assert result["name"] == "__main__"
    assert Path.cwd() == original_cwd
    assert sys.argv == original_argv
