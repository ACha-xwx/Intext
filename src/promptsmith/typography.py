"""In-memory UI fonts derived from Tk platform defaults; no font files."""
from __future__ import annotations

import logging
import tkinter.font as tkfont

LOG = logging.getLogger(__name__)
UI_SCALE = 1.25


class Typography:
    def __init__(self, root, values):
        self.root = root
        self.fonts = {}
        root._promptsmith_typography = self
        self.apply(values)

    def apply(self, values):
        # Read the platform default rather than changing Tk's named fonts or
        # selecting a particular installed family. Tk handles glyph fallback.
        self.base = tkfont.nametofont("TkDefaultFont", self.root).actual()
        self.family = self.base["family"]
        self.values = {"font_size": values["font_size"]}
        for (size, weight, slant, scale), font in self.fonts.items():
            font.configure(**{**self.base, "size": self._size(size, scale), "weight": weight, "slant": slant})
        self.root.option_add("*Font", str(self.font()), 80)
        self.root.option_add("*TCombobox*Listbox.font", str(self.font()), 80)
        LOG.info("Native UI typography applied: source=TkDefaultFont family=%s base_pt=%s scale=%.2f display_pt=%s; font generation disabled",
                 self.family, self.values["font_size"], UI_SCALE, self._size("body"))

    def close(self):
        LOG.debug("Native UI typography closed: in-memory fonts=%s", len(self.fonts))

    def _size(self, size, scale=UI_SCALE):
        base = {"body": self.values["font_size"], "title": max(17, self.values["font_size"]+4),
                "heading": max(9, self.values["font_size"]-1)}.get(size, size)
        return round(base * scale)

    def font(self, size="body", weight="normal", slant="roman", *, scale=UI_SCALE):
        key = (size, weight, slant, scale)
        if key not in self.fonts:
            self.fonts[key] = tkfont.Font(self.root, **{**self.base, "size": self._size(size, scale),
                                                       "weight": weight, "slant": slant})
        return self.fonts[key]


def ui_font(widget, size="body", weight="normal"):
    current = widget
    scale = None
    while current is not None:
        # A popup can use its original sizes without altering shared fonts or
        # Tk's global defaults. Descendants inherit the closest local scope.
        if scale is None:
            scale = getattr(current, "_promptsmith_font_scale", None)
        manager = getattr(current, "_promptsmith_typography", None)
        if manager is not None:
            return manager.font(size, weight, scale=UI_SCALE if scale is None else scale)
        current = getattr(current, "master", None)
    # Tuple fallback keeps its font specification alive without owning a
    # temporary Font object; standalone dialogs use the platform default too.
    base = tkfont.nametofont("TkDefaultFont", widget).actual()
    point_size = {"body": base["size"], "title": max(17, base["size"]+4),
                  "heading": max(9, base["size"]-1)}.get(size, size)
    return (base["family"], round(point_size * (UI_SCALE if scale is None else scale)), weight)
