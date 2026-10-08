from pathlib import Path

from promptsmith.m1 import M1Assets, m1_system_prompt


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


def test_current_m1_assets_include_v022_bridge_rules() -> None:
    assets = M1Assets.load(DESIGN)
    assert assets.prompt_version == "M1_system_v0.22"
    assert "不要要求用户先写出术语正式全称" in assets.system_prompt
    assert "旧的 max_questions、remaining_rounds、allow_questions" in assets.system_prompt


def test_current_incremental_assets_include_v015_bridge_rules() -> None:
    assets = M1Assets.load(DESIGN)
    prompt = m1_system_prompt(assets.system_prompt, mode="incremental")
    assert "语义不完整不是 input_error" in prompt
    assert "你自己查一下" in prompt
