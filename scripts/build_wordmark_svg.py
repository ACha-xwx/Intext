"""Offline artwork + font outlines; these dependencies are never used at startup.

Usage: python scripts/build_wordmark_svg.py chinese.png orange-juice.ttf output.svg
Requires build-only opencv-python and fonttools. No font or bitmap is embedded.
"""
import argparse
from hashlib import sha256
from pathlib import Path
from xml.sax.saxutils import escape

import cv2
import numpy as np
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


def chinese_outline(image_path, height):
    # imdecode accepts Unicode Windows paths, unlike some OpenCV imread builds.
    gray = cv2.imdecode(np.frombuffer(image_path.read_bytes(), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError("Cannot read Chinese artwork")
    _, mask = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    keep = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= 80]
    mask = np.isin(labels, keep).astype(np.uint8) * 255
    if not keep:
        raise ValueError("No ink found in Chinese artwork")
    x, y, width, ink_height = cv2.boundingRect(mask)
    scale = height / ink_height
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    paths = []
    for contour in contours:
        points = cv2.approxPolyDP(contour, 0.65, True).reshape(-1, 2)
        if len(points) < 3:
            continue
        coordinates = [(6 + (px-x)*scale, 6 + (py-y)*scale) for px, py in points]
        paths.append("M" + "L".join(f"{px:.2f},{py:.2f}" for px, py in coordinates) + "Z")
    return "".join(paths), width * scale


def font_outline(font, text, height, left, top):
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    layout, advance = [], 0
    for character in text:
        name = cmap.get(ord(character))
        if name is None:
            raise ValueError(f"Font lacks {character!r}")
        layout.append((name, advance))
        advance += font["hmtx"][name][0] + 45
    bounds = BoundsPen(glyphs)
    for name, offset in layout:
        glyphs[name].draw(TransformPen(bounds, (1, 0, 0, 1, offset, 0)))
    xmin, ymin, xmax, ymax = bounds.bounds
    scale = height / (ymax-ymin)
    pen = SVGPathPen(glyphs, ntos=lambda value: f"{value:.2f}".rstrip("0").rstrip("."))
    for name, offset in layout:
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale,
                                           left + (offset-xmin)*scale, top+ymax*scale)))
    return pen.getCommands(), (xmax-xmin)*scale


def build(image_path, font_path, destination):
    chinese_height, english_height, dot_height, gap = 170, 164, 22, 34
    chinese, chinese_width = chinese_outline(image_path, chinese_height)
    with TTFont(font_path) as font:
        dot, dot_width = font_outline(font, "·", dot_height, 6+chinese_width+gap,
                                      6+(chinese_height-dot_height)/2)
        english, english_width = font_outline(font, "Intext", english_height,
                                              6+chinese_width+gap+dot_width+gap,
                                              6+(chinese_height-english_height)/2)
    width = 12+chinese_width+gap+dot_width+gap+english_width
    source_hash = sha256(image_path.read_bytes()).hexdigest()
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} {chinese_height+12}" width="{width:.2f}" height="{chinese_height+12}" role="img" aria-labelledby="title description">
  <title id="title">意织 · Intext</title>
  <desc id="description">用户提供的中文手绘描边与排线，组合 Orange Juice 英文字轮廓。透明背景，无嵌入字体或位图。</desc>
  <metadata>Chinese source SHA-256: {escape(source_hash)}. Orange Juice: Copyright (c) 2013 by Brittney Murphy. Free for personal and non-profit use. Commercial use is $5.</metadata>
  <g fill="#18181b">
    <path id="chinese" fill-rule="evenodd" d="{chinese}"/>
    <path id="separator" d="{dot}"/>
    <path id="english" d="{english}"/>
  </g>
</svg>
'''
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(svg, encoding="utf-8")
    print(f"Wordmark: {destination}, {width:.2f} x {chinese_height+12}, {len(svg.encode('utf-8'))} bytes")


def build_english(font_path, destination):
    """Export the same English lettering for the monochrome sidebar brand."""
    with TTFont(font_path) as font:
        outline, ink_width = font_outline(font, "Intext", 164, 6, 6)
    width = ink_width + 12
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} 176" width="{width:.2f}" height="176" role="img" aria-labelledby="title">
  <title id="title">Intext</title>
  <metadata>Orange Juice: Copyright (c) 2013 by Brittney Murphy. Free for personal and non-profit use. Commercial use is $5.</metadata>
  <path fill="#18181b" d="{outline}"/>
</svg>
'''
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artwork", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--english-output", type=Path)
    args = parser.parse_args()
    build(args.artwork, args.font, args.output)
    if args.english_output:
        build_english(args.font, args.english_output)
