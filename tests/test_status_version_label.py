"""Guard the status-bar version label against silent drift.

The label used to be a hard-coded string in ``ui.py``; when the M1 prompt was
bumped to v0.8 the label still said v0.6 for several revisions.  These checks
are deliberately headless -- they assert the asset constants and the rendered
text, not a Tk widget, so they still run in environments without a display.
"""

from __future__ import annotations

import re
from pathlib import Path

from promptsmith.m1 import M1Assets
from promptsmith.m2 import M2Assets
from promptsmith.m5 import M5Assets


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "promptsmith" / "ui.py"


def _status_label_text() -> str:
    """Reproduce what ``PromptSmithApp._status_versions_text`` renders.

    Kept free of Tk so the assertion works headless; ``ui.py`` cannot be imported
    without a display.
    """
    parts = []
    for assets in (M1Assets, M2Assets, M5Assets):
        module = assets.prompt_version.split("_")[0]
        suffix = assets.prompt_version.removeprefix(f"{module}_system_")
        parts.append(f"{module} {suffix} / {assets.contract_version}")
    return " · ".join(parts)


def test_status_label_matches_the_loaded_prompt_assets() -> None:
    text = _status_label_text()

    assert text == "M1 v0.11 / m1.v0.2 · M2 v0.2 / m2.v0.1 · M5 v0.2 / m5.v0.1"
    for assets in (M1Assets, M2Assets, M5Assets):
        assert assets.contract_version in text


def test_status_label_is_not_hard_coded_in_the_source() -> None:
    """The label must be derived, so a prompt bump cannot leave it stale."""
    source = UI.read_text(encoding="utf-8")

    assert "M1 v0.6" not in source
    assert "M1 v0.5" not in source
    # A literal "M1 v0.8" is equally wrong: it would drift again on the next bump.
    assert not re.search(r'"M1 v\d', source)
    assert "self._status_versions_text()" in source


def test_m1_current_prompt_file_exists_and_matches_the_declared_version() -> None:
    design = ROOT / "resources" / "prompts"

    assert M1Assets.prompt_version == "M1_system_v0.11"
    assert (design / f"{M1Assets.prompt_version}.txt").is_file()
    assert M1Assets.contract_version == "m1.v0.2"
    assert (design / "M1_input_v0.2.schema.json").is_file()
    assert (design / "M1_output_v0.2.schema.json").is_file()
