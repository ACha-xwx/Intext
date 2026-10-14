"""Opt-in compiled installer tests at the setup CLI and Windows registry boundary.

INTEXT_ISCC points at ISCC.exe. Private registry identities and external runtime
fixtures keep these checks independent of the shared Microsoft installation.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import uuid
import winreg

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not os.environ.get("INTEXT_ISCC"), reason="requires Windows Inno Setup compiler")


def command(arguments, timeout=60):
    return subprocess.run(arguments, capture_output=True, timeout=timeout)


@pytest.fixture
def setup_fixture(tmp_path):
    identity = str(uuid.uuid4())
    registry = rf"Software\IntextInstallerTests\{identity}"
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "Intext.exe").write_bytes(b"fixture payload, not a running application")
    (payload / "_internal").mkdir()
    (payload / "_internal" / "fixture.txt").write_text("all bundled resources", encoding="utf-8")
    marker = tmp_path / "runtime-arguments.txt"
    runtime = tmp_path / "runtime.exe"

    def compile_installer(runtime_exit=0, register=True, reserve=512):
        source = tmp_path / "runtime.cs"
        source.write_text(
            'using System; using System.IO; using Microsoft.Win32; class Fixture {'
            'static int Main(string[] args) {'
            f'File.WriteAllText(@"{marker}", String.Join(" ", args));'
            + (f'using (var key = Registry.CurrentUser.CreateSubKey(@"{registry}")) {{ key.SetValue("pv", "155.0.0.0"); }}' if register else '')
            + f'return {runtime_exit}; }} }}', encoding="utf-8")
        csc = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        compilation = command([str(csc), "/nologo", "/target:winexe", f"/out:{runtime}", str(source)])
        assert compilation.returncode == 0, compilation.stdout
        output = tmp_path / "compiled"
        compilation = command([
            os.environ["INTEXT_ISCC"], f"/DAppId={{{identity}}}",
            "/DAppName=Intext installer test", f"/DPayloadDir={payload}",
            f"/DRuntimeInstaller={runtime}", f"/DRuntimeKey={registry}",
            f"/DSystemReserveMB={reserve}", f"/DOutputDir={output}",
            "/DOutputName=Setup", str(ROOT / "installer/Intext.iss"),
        ])
        assert compilation.returncode == 0, (compilation.stdout, compilation.stderr)
        return output / "Setup.exe"

    target = tmp_path / "installed"
    log = tmp_path / "setup.log"

    def install(installer):
        return command([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                        "/SP-", "/TASKS=", f"/DIR={target}", f"/LOG={log}"], timeout=90)

    yield compile_installer, install, target, registry, marker, log
    if (target / "unins000.exe").exists():
        uninstall = command([str(target / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
        assert uninstall.returncode == 0, uninstall.stderr
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, registry)
    except FileNotFoundError:
        pass


def test_installer_skips_already_available_runtime(setup_fixture):
    build, install, target, registry, marker, log = setup_fixture
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry) as key:
        winreg.SetValueEx(key, "pv", 0, winreg.REG_SZ, "155.0.0.0")
    result = install(build())
    assert result.returncode == 0, log.read_text(encoding="utf-8-sig")
    assert (target / "_internal/fixture.txt").read_text() == "all bundled resources"
    assert not marker.exists()


def test_installer_installs_missing_runtime_and_rechecks_it(setup_fixture):
    build, install, target, registry, marker, log = setup_fixture
    result = install(build())
    assert result.returncode == 0, log.read_text(encoding="utf-8-sig")
    assert marker.read_text() == "/silent /install"
    assert (target / "Intext.exe").exists()


@pytest.mark.parametrize("exit_code,register", [(7, False), (0, False)])
def test_runtime_failure_does_not_leave_an_apparently_installed_application(setup_fixture, exit_code, register):
    build, install, target, registry, marker, log = setup_fixture
    result = install(build(runtime_exit=exit_code, register=register))
    assert result.returncode != 0
    assert marker.exists()
    assert not (target / "Intext.exe").exists()
    assert "Intext prerequisites:" in log.read_text(encoding="utf-8-sig")


def test_low_space_blocks_before_runtime_or_application_install(setup_fixture):
    build, install, target, registry, marker, log = setup_fixture
    result = install(build(reserve=4_000_000_000))
    assert result.returncode != 0
    assert not marker.exists()
    assert not (target / "Intext.exe").exists()
    assert "insufficient system space" in log.read_text(encoding="utf-8-sig")
