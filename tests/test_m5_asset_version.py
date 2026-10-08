import json
from pathlib import Path

from promptsmith.m5 import M5Assets


def test_current_m5_prompt_revision_keeps_the_existing_contract_and_old_prompt():
    design = Path(__file__).resolve().parents[1] / "resources/prompts"
    assets = M5Assets.load(design)
    assert assets.prompt_version == "M5_system_v0.2"
    assert assets.contract_version == "m5.v0.1"
    assert assets.system_prompt == (design / "M5_system_v0.2.txt").read_text(encoding="utf-8-sig")
    assert (design / "M5_system_v0.1.txt").is_file()
    for direction in ("input", "output"):
        schema = json.loads((design / f"M5_{direction}_v0.1.schema.json").read_text(encoding="utf-8-sig"))
        assert getattr(assets, f"{direction}_schema") == schema
