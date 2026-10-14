"""Opt-in public deployment checks; run against an actual frozen executable."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time

import pytest


@pytest.mark.skipif(not os.environ.get("INTEXT_TEST_APP"), reason="requires a built Windows executable")
def test_installed_application_starts_without_unpacking_to_temp(tmp_path):
    executable = Path(os.environ["INTEXT_TEST_APP"]).resolve()
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    environment = dict(os.environ, TEMP=str(temporary), TMP=str(temporary),
                       LOCALAPPDATA=str(tmp_path / "data"), PYTHONNOUSERSITE="1")
    process = subprocess.Popen([str(executable), "--smoke-test"], env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    extracted = False
    try:
        deadline = time.monotonic() + 30
        while process.poll() is None and time.monotonic() < deadline:
            extracted |= any(temporary.glob("_MEI*"))
            time.sleep(.01)
        output, errors = process.communicate(timeout=5)
        assert process.returncode == 0, (output, errors)
        assert not extracted, "Startup extracts the bundle into TEMP, which fails on the reported 98 MB free disk"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
