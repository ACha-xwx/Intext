"""Exercise the Windows launcher through cmd, without opening product windows."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows batch entry")
REPOSITORY = Path(__file__).resolve().parents[1]


def launch_fixture(tmp_path, *, virtualenv=False, arguments=(), exit_code=0):
    project = tmp_path / "Project with spaces"
    project.mkdir()
    shutil.copy2(REPOSITORY / "run.bat", project / "run.bat")
    (project / "run_promptsmith.py").write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path('launch.json').write_text(json.dumps({'cwd': os.getcwd(), "
        "'python': sys.executable, 'argv': sys.argv[1:]}), encoding='utf-8')\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    if virtualenv:
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(project / ".venv")],
                       check=True, capture_output=True, timeout=30)
    environment = dict(os.environ)
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
    result = subprocess.run(
        [environment.get("COMSPEC", "cmd.exe"), "/d", "/c", "call", str(project / "run.bat"), *arguments],
        cwd=tmp_path, env=environment, input="\n", capture_output=True, text=True, timeout=15,
    )
    record = project / "launch.json"
    return result, json.loads(record.read_text(encoding="utf-8")) if record.exists() else None, project


def test_launcher_uses_project_virtualenv_and_web_from_another_directory(tmp_path):
    result, record, project = launch_fixture(tmp_path, virtualenv=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert record is not None, result.stdout + result.stderr
    assert Path(record["cwd"]) == project
    assert Path(record["python"]) == project / ".venv" / "Scripts" / "python.exe"
    assert record["argv"] == ["--renderer", "web"]


def test_launcher_without_virtualenv_uses_path_python_and_forwards_override(tmp_path):
    result, record, project = launch_fixture(tmp_path, arguments=("--renderer", "tk", "--smoke-test"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert record["argv"] == ["--renderer", "web", "--renderer", "tk", "--smoke-test"]
    assert Path(record["python"]) == Path(sys.executable)
    assert Path(record["cwd"]) == project


def test_launcher_preserves_failure_and_displays_dependency_repair(tmp_path):
    result, record, _ = launch_fixture(tmp_path, exit_code=7)
    assert record is not None
    assert result.returncode == 7
    assert "-m pip install -r requirements.txt" in result.stdout
    assert "WebView2 Runtime" in result.stdout


def test_explicit_web_without_site_packages_reports_same_python_install_command(tmp_path):
    environment = dict(os.environ, LOCALAPPDATA=str(tmp_path), PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, "-B", "-S", str(REPOSITORY / "run_promptsmith.py"), "--renderer", "web"],
        cwd=REPOSITORY, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode != 0
    assert "No module named 'webview'" in result.stderr
    assert f'"{sys.executable}" -m pip install -r requirements.txt' in result.stderr
    assert "Tk renderer" not in result.stdout + result.stderr
    assert not (tmp_path / "PromptSmith" / "logs").exists()
