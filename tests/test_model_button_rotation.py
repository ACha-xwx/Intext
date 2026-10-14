"""The model menu arrow stays in place while opening and closing."""
from io import BytesIO

import pytest
from PIL import Image

from tests.test_frontend_review_regressions import browser, page, load


def arrow_ink_center(page, arrow, theme):
    bounds = arrow.bounding_box()
    image = Image.open(BytesIO(arrow.screenshot())).convert("RGB")
    points = [(x, y) for y in range(image.height) for x in range(image.width)
              if (max(image.getpixel((x, y))) < 130 if theme == "light"
                  else min(image.getpixel((x, y))) > 150)]
    assert points, "The menu arrow must be visible"
    return (bounds["x"] + (min(x for x, _ in points) + max(x for x, _ in points)) / 2,
            bounds["y"] + (min(y for _, y in points) + max(y for _, y in points)) / 2)


def rotate_and_check_anchor(page, button, anchor):
    button.click()
    frames = page.evaluate("""() => new Promise(resolve => {
      const arrow=document.querySelector('#model-button').lastElementChild;
      const frames=[], started=performance.now();
      function sample(now) {
        const rect=arrow.getBoundingClientRect();
        frames.push([rect.x+rect.width/2, rect.y+rect.height/2]);
        if(now-started<450) requestAnimationFrame(sample); else resolve(frames);
      }
      requestAnimationFrame(sample);
    })""")
    assert len(frames) > 2
    assert all(abs(x-anchor[0]) < .1 and abs(y-anchor[1]) < .1 for x, y in frames)


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("font_size", [9, 12, 18])
def test_model_arrow_rotates_without_moving_its_visible_center(page, theme, font_size):
    load(page, theme=theme, font_size=font_size)
    button = page.locator("#model-button")
    arrow = button.locator(":scope > :last-child")
    closed = arrow_ink_center(page, arrow, theme)
    box = button.bounding_box()
    assert abs(closed[1] - (box["y"] + box["height"] / 2)) < 1
    bounds = arrow.bounding_box()
    anchor = (bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2)
    rotate_and_check_anchor(page, button, anchor)
    opened = arrow_ink_center(page, arrow, theme)
    assert abs(closed[0] - opened[0]) < 1
    assert abs(closed[1] - opened[1]) < 1
    rotate_and_check_anchor(page, button, anchor)
    restored = arrow_ink_center(page, arrow, theme)
    assert abs(closed[0] - restored[0]) < 1
    assert abs(closed[1] - restored[1]) < 1
