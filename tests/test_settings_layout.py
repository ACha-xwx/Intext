"""Settings label/control correspondence at the production browser boundary."""

import pytest

from tests.test_frontend_review_regressions import browser, page, load
from tests.test_custom_provider_browser import custom_state


@pytest.mark.parametrize("theme,width,font", [("light", 1440, 12), ("dark", 1440, 12),
                                              ("dark", 824, 12), ("light", 824, 18),
                                              ("dark", 720, 12), ("light", 720, 18)])
def test_custom_delete_action_keeps_each_model_parameter_on_its_own_labeled_row(page, theme, width, font):
    page.set_viewport_size({"width": width, "height": 654})
    settings = custom_state(page, theme=theme, font_size=font)
    for provider in ["OpenAI", "GPT中转", "OpenAI"]:
        settings["connection"].update(provider=provider, model_provider="OpenAI")
        load(page, page="settings", theme=theme, font_size=font, settings=settings)
        assert page.get_by_role("button", name="删除供应商", exact=True).is_visible() == (provider == "GPT中转")
        for key, spec in settings["fields"].items():
            if spec["category"] != "模型":
                continue
            control = page.get_by_label(spec["label"], exact=True)
            control.scroll_into_view_if_needed()
            label = page.locator(f'label[for="settings-field-{key}"]').bounding_box()
            box = control.bounding_box()
            if width > 760:
                assert label["x"] + label["width"] <= box["x"]
                assert abs(label["y"] + label["height"]/2 - (box["y"] + box["height"]/2)) <= 1
            else:
                assert abs(label["x"] - box["x"]) <= 1
                assert 0 <= box["y"] - (label["y"] + label["height"]) <= 10
    events = page.evaluate("calls.filter(c=>c.action==='diagnostic'&&c.args[1]==='settings fields rendered')")
    assert len(events) == 1
    assert "full_width_actions=2" in events[0]["args"][2]
