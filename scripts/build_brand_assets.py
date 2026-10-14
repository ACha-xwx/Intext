"""Prepare the user-supplied Intext logo offline; not part of app startup."""
import argparse
from pathlib import Path
from PIL import Image


def build(source, destination):
    image = Image.open(source).convert("RGB")
    pixels = []
    for red, green, blue in image.getdata():
        alpha = min(255, max(0, round((250 - min(red, green, blue)) * 255 / 20)))
        if alpha:
            # Remove the white matte from partially transparent edge pixels.
            rgb = tuple(max(0, min(255, round((channel - 255 * (1-alpha/255)) / (alpha/255))))
                        for channel in (red, green, blue))
            pixels.append((*rgb, alpha))
        else:
            pixels.append((0, 0, 0, 0))
    transparent = Image.new("RGBA", image.size)
    transparent.putdata(pixels)
    transparent = transparent.crop(transparent.getbbox())
    transparent.thumbnail((704, 704), Image.Resampling.LANCZOS)
    logo = Image.new("RGBA", (768, 768))
    logo.alpha_composite(transparent, ((768-transparent.width)//2, (768-transparent.height)//2))
    destination.mkdir(parents=True, exist_ok=True)
    logo.save(destination / "intext-logo.png", optimize=True)
    logo.save(destination / "intext.ico", sizes=[(size,size) for size in (16,24,32,48,64,128,256)])
    logo.resize((32,32), Image.Resampling.LANCZOS).save(destination / "intext-logo-32.png")
    print("Created transparent logo, Tk mark and 7-size Windows icon")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--destination", type=Path,
        default=Path(__file__).resolve().parents[1]/"resources/ui/workspace/brand")
    args = parser.parse_args()
    build(args.source, args.destination)
