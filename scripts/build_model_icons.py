"""Render checked-in provider SVGs for Tk. Development-only: pip install cairosvg."""
from pathlib import Path


def main():
    import cairosvg
    directory = Path(__file__).resolve().parents[1] / "resources/ui"
    for group in ("model_icons", "action_icons"):
        for source in (directory / group).glob("*.svg"):
            svg = source.read_text(encoding="utf-8")
            light = svg.replace("currentColor", "#18181b")
            dark = svg.replace("#26282c", "#fafafa").replace("currentColor", "#fafafa")
            for suffix, content in (("", light), ("_dark", dark)):
                cairosvg.svg2png(bytestring=content.encode("utf-8"),
                                write_to=str(source.with_name(source.stem+suffix+".png")),
                                output_width=72, output_height=72)
            print(group, source.name)


if __name__ == "__main__":
    main()
