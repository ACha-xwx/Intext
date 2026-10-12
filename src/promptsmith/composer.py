"""Native Tk replicas of the supplied prompt composer and model picker.

The widget owns presentation only; settings and task state stay on the app.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from urllib.parse import urlsplit
from PIL import Image, ImageDraw, ImageTk

from .model_catalog import (EFFORTS, EFFORT_LABELS, PROVIDERS, PROVIDER_LABELS,
                            PROVIDER_PRESETS, effort_note, find_model,
                            search_models)
from .paths import resource_root
from .typography import ui_font
from .display import display_scale

LOG = logging.getLogger(__name__)
BG = "#ffffff"
MUTED = "#f2f2f5"
BORDER = "#dedee3"
INK = "#27272a"
SUBTLE = "#71717a"


@dataclass(frozen=True)
class Palette:
    bg: str
    muted: str
    border: str
    ink: str
    subtle: str
    placeholder: str
    focus: str
    shadow: str
    send: str
    send_ink: str
    disabled: str
    disabled_ink: str

    @property
    def base(self):
        return self.bg, self.muted, self.border, self.ink, self.subtle


THEMES = {
    "light": Palette(BG, "#f4f4f5", "#e4e4e7", "#18181b", SUBTLE, "#a1a1aa",
                     "#b6b6c1", "#e6e6ea", "#282828", "#ffffff", "#f4f4f5", "#a1a1aa"),
    "dark": Palette("#171717", "#262626", "#303030", "#fafafa", "#a3a3a3", "#737373",
                    "#525252", "#101010", "#fafafa", "#171717", "#262626", "#737373"),
}


def clipped_text(font, text, width):
    """Fit long labels with logarithmic measurements instead of one per char."""
    width = max(20, width)
    if font.measure(text) <= width:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low+high+1)//2
        if font.measure(text[:middle]+"…") <= width:
            low = middle
        else:
            high = middle-1
    return text[:low]+"…"


def rounded(canvas, box, radius=20, **options):
    x1, y1, x2, y2 = box
    r = min(radius, (x2-x1)/2, (y2-y1)/2)
    k = .5522847498*r
    points = (
        x1+r, y1,
        x1+r, y1, x2-r, y1, x2-r, y1,
        x2-r+k, y1, x2, y1+r-k, x2, y1+r,
        x2, y1+r, x2, y2-r, x2, y2-r,
        x2, y2-r+k, x2-r+k, y2, x2-r, y2,
        x2-r, y2, x1+r, y2, x1+r, y2,
        x1+r-k, y2, x1, y2-r+k, x1, y2-r,
        x1, y2-r, x1, y1+r, x1, y1+r,
        x1, y1+r-k, x1+r-k, y1, x1+r, y1,
    )
    return canvas.create_polygon(*points, smooth="raw", splinesteps=24, **options)


class GlyphButton(tk.Canvas):
    """Focus-capable pill/circle with the same invoke/state contract as a button."""
    def __init__(self, master, *, text="", command, arrow=False, choice=False, provider=False, width=40, height=40, palette=None, **kw):
        self.palette = palette or THEMES["light"]
        BG, MUTED, BORDER, INK, SUBTLE = self.palette.base
        super().__init__(master, width=width, height=height, bg=kw.pop("bg", BG),
                         highlightthickness=0, takefocus=True, cursor="hand2", **kw)
        self.text, self.command, self.arrow = text, command, arrow
        self.stop = False
        self.choice, self.selected = choice, False
        self.provider = provider
        self.expanded = False
        self.icon = None
        self.level = -1
        self.hover = self.focused = False
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", lambda _e: self._hover(True))
        self.bind("<Leave>", lambda _e: self._hover(False))
        self.bind("<FocusIn>", lambda _e: self._focus(True))
        self.bind("<FocusOut>", lambda _e: self._focus(False))
        self.bind("<Button-1>", lambda _e: self.invoke())
        self.bind("<Return>", self._keyboard)
        self.bind("<space>", self._keyboard)

    def configure(self, cnf=None, **kw):
        result = super().configure(cnf, **kw)
        if kw:
            self._draw()
        return result

    config = configure

    def invoke(self):
        if str(self.cget("state")) != "disabled":
            return self.command()

    def _keyboard(self, _event):
        self.invoke()
        return "break"

    def _hover(self, value):
        self.hover = value
        self._draw()

    def _focus(self, value):
        self.focused = value
        self._draw()

    def _draw(self, _event=None):
        BG, MUTED, BORDER, INK, SUBTLE = self.palette.base
        w, h = max(self.winfo_width(), int(self.cget("width"))), int(self.cget("height"))
        disabled = str(self.cget("state")) == "disabled"
        font = ui_font(self, 11)
        signature = (w, h, disabled, self.palette, self.text, str(self.icon), self.level,
                     self.expanded, self.hover, self.focused, self.selected, self.stop, tuple(font.actual().items()))
        if signature == getattr(self, "_draw_signature", None):
            return
        self._draw_signature = signature
        self.delete("all")
        if self.arrow:
            self.create_oval(2, 2, w-2, h-2, fill=self.palette.disabled if disabled else self.palette.send, outline="")
            color = self.palette.disabled_ink if disabled else self.palette.send_ink
            x, y = w/2, h/2
            if self.stop:
                self.create_rectangle(x-5, y-5, x+5, y+5, fill=color, outline="")
            else:
                self.create_line(x, y+6, x, y-6, fill=color, width=2)
                self.create_line(x-5, y-1, x, y-6, x+5, y-1, fill=color, width=2, joinstyle="round")
        elif self.provider:
            rounded(self, (1, 1, w-1, h-1), 12,
                    fill=BG if self.selected or self.hover else MUTED,
                    outline=BORDER if self.selected else "")
            if self.icon:
                self.create_image(w/2, h/2, image=self.icon)
            else:
                self.create_polygon(w/2, h/2-8, w/2+8, h/2, w/2, h/2+8, w/2-8, h/2,
                                    fill="", outline=INK, width=1.5)
        elif self.choice:
            rounded(self, (1, 1, w-1, h-1), h/2,
                    fill=BG if self.selected else MUTED, outline=BORDER if self.selected else "")
            self.create_text(w/2, h/2, text=self.text, font=font, fill=INK if self.selected else SUBTLE)
        else:
            rounded(self, (1, 1, w-1, h-1), h/2,
                    fill=MUTED if self.hover else BG, outline=BORDER)
            left = 12
            if self.icon:
                self.create_image(25, h/2, image=self.icon)
                left = 44
            # Match the replica's truncated model label while retaining the
            # full model name in the picker and in self.text.
            reserve = 65 if self.level >= 0 else 24
            label = clipped_text(font, self.text, w-left-reserve)
            self.create_text(left, h/2, text=label, anchor="w", font=font, fill=SUBTLE if disabled else INK)
            if self.level >= 0:
                for i in range(4):
                    self.create_line(w-59+i*5, h/2+5, w-59+i*5, h/2+5-(i+1)*3,
                                     width=3, fill=INK if i <= self.level else BORDER)
            direction = -1 if self.expanded else 1
            self.create_line(w-23, h/2-2*direction, w-19, h/2+2*direction, w-15, h/2-2*direction,
                             fill=SUBTLE, width=1.5)
        if self.focused:
            rounded(self, (1, 1, w-1, h-1), 12 if self.provider else h/2,
                    fill="", outline=self.palette.focus, width=2)


class SlimScrollbar(tk.Canvas):
    """A themed, draggable scrollbar shown only when the model list overflows."""
    def __init__(self, master, palette, command):
        # The content determines height. Canvas's default ~276px can enlarge
        # a short Text, hide its scrollbar, then shrink it and show it again.
        super().__init__(master, width=8, height=1, bg=palette.bg, highlightthickness=0, cursor="arrow")
        self.palette, self.command = palette, command
        self.first, self.last = 0., 1.
        self._drag_offset = 0
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        if self.last-self.first >= .999:
            self.grid_remove()
        else:
            self.grid()
        self._draw()

    def _draw(self):
        self.delete("all")
        height = max(1, self.winfo_height())
        self._top = self.first*height
        self._bottom = min(height, max(self._top+12, self.last*height))
        rounded(self, (2, self._top, 6, self._bottom), 2, fill=self.palette.focus, outline="")

    def _press(self, event):
        if self._top <= event.y <= self._bottom:
            self._drag_offset = event.y-self._top
        else:
            self._drag_offset = (self._bottom-self._top)/2
            self._drag(event)
        return "break"

    def _drag(self, event):
        fraction = (event.y-self._drag_offset)/max(1, self.winfo_height())
        self.command("moveto", max(0., min(1.-(self.last-self.first), fraction)))
        return "break"


class ComposerText(tk.Text):
    """Notify on typing, paste, undo and programmatic edits, without polling."""
    def __init__(self, master, changed, **kw):
        super().__init__(master, **kw)
        self.changed = changed
        self.edit_modified(False)
        self.bind("<<Modified>>", self._modified, add="+")

    def _modified(self, _event=None):
        if self.edit_modified():
            self.edit_modified(False)
            self.changed()

    def insert(self, *args):
        result = super().insert(*args)
        self.changed()
        return result

    def delete(self, *args):
        result = super().delete(*args)
        self.changed()
        return result

    def replace(self, *args):
        result = super().replace(*args)
        self.changed()
        return result


class PromptComposer(tk.Canvas):
    def __init__(self, master, app):
        self.app = app
        self.theme_name = app.preferences["composer_theme"]
        self.palette = THEMES[self.theme_name]
        BG, MUTED, BORDER, INK, SUBTLE = self.palette.base
        super().__init__(master, bg=BG, highlightthickness=0, height=132)
        self.icons = {}
        self.picker = None
        self._cached_picker = None
        self._resize_id = self._placeholder_id = None
        self._traces = []
        self._placeholder_index = 0
        self.focused = False
        self._load_icons()
        self.body = tk.Frame(self, bg=BG)
        self.body.columnconfigure(0, weight=1)
        self.window = self.create_window(18, 15, window=self.body, anchor="nw")
        self.entry = ComposerText(self.body, self.changed, width=1, height=2, wrap="word", undo=True,
                                  relief="flat", borderwidth=0, highlightthickness=0,
                                  bg=BG, fg=INK, insertbackground=INK, padx=2, pady=4,
                                  font=ui_font(self), cursor="xterm")
        self.entry.grid(row=0, column=0, sticky="ew")
        self.placeholder = tk.Label(self.body, text="描述你想完成的目标…", fg=self.palette.placeholder, bg=BG,
                                    font=ui_font(self), anchor="w", padx=0, pady=0, bd=0, cursor="xterm")
        self.entry.bind("<Configure>", lambda _e: self.after_idle(self._place_placeholder), add="+")
        self.placeholder.bind("<Button-1>", lambda _e: self.entry.focus_set())
        self.entry.bind("<Return>", app._conversation_enter)
        self.entry.bind("<Shift-Return>", lambda _e: None)
        self.entry.bind("<FocusIn>", lambda _e: self._focus(True), add="+")
        self.entry.bind("<FocusOut>", lambda _e: self._focus(False), add="+")
        self.divider = tk.Frame(self.body, bg=BORDER, height=1)
        self.divider.grid(row=1, column=0, sticky="ew", pady=(10, 9))
        self.toolbar = tk.Frame(self.body, bg=BG)
        self.toolbar.grid(row=2, column=0, sticky="ew")
        self.toolbar.columnconfigure(0, weight=1)
        self.model_button = GlyphButton(self.toolbar, text="选择模型", command=self.toggle_picker, width=265, height=42, palette=self.palette)
        self.model_button.grid(row=0, column=0, sticky="w")
        from .interaction_ui import GlassButton
        self.choice_menu = None
        self.depth_button = GlassButton(self.toolbar, text="整理深度", command=lambda: self.toggle_choices("depth"), palette=self.palette)
        self.depth_button.grid(row=0, column=1, padx=(10, 0))
        self.category_button = GlassButton(self.toolbar, text="任务类型", command=lambda: self.toggle_choices("category"), palette=self.palette)
        self.category_button.grid(row=0, column=2, padx=(8, 0))
        self.send_button = GlyphButton(self.toolbar, text="发送消息", command=app.send_conversation_message,
                                       arrow=True, width=42, height=42, state="disabled", palette=self.palette)
        self.send_button.grid(row=0, column=3, padx=(12, 0))
        self.bind("<Configure>", self._fit, add="+")
        self.bind("<Destroy>", self._destroyed, add="+")
        for var in (app.provider_var, app.api_model_var, app.api_base_var, app.protocol_var,
                    app.preference_vars["reasoning_effort"]):
            self._traces.append((var, var.trace_add("write", lambda *_a: self.refresh())))
        self.refresh()
        self._placeholder_id = self.after(3200, self._rotate_placeholder)
        LOG.info("Prompt composer ready; model picker and persistent send button enabled")

    def _load_icons(self):
        started = time.perf_counter()
        suffix = "_dark.png" if self.theme_name == "dark" else ".png"
        size = round(24*display_scale(self.app.root))
        for provider in PROVIDERS:
            path = resource_root() / "resources/ui/model_icons" / (provider.lower() + suffix)
            try:
                with Image.open(path) as source:
                    self.icons[provider] = ImageTk.PhotoImage(source.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS), master=self)
            except (tk.TclError, OSError, ValueError):
                LOG.warning("Model icon unavailable: provider=%s path=%s", provider, path, exc_info=True)
        # The checkmark must not inherit a math or CJK font's baseline/shape.
        check = Image.new("RGBA", (80, 80))
        ImageDraw.Draw(check).line([(18, 40), (33, 55), (62, 25)], fill=self.palette.ink, width=7, joint="curve")
        self.check_icon = ImageTk.PhotoImage(check.resize((20, 20), Image.Resampling.LANCZOS), master=self)
        LOG.debug("Composer icons prepared: density=%.2f size=%s elapsed_ms=%.2f", display_scale(self.app.root), size,
                  (time.perf_counter()-started)*1000)

    def apply_theme(self):
        name = self.app.preferences["composer_theme"]
        if name == self.theme_name:
            return
        self.discard_picker()
        self.theme_name, self.palette = name, THEMES[name]
        self.configure(bg=self.palette.bg)
        self.body.configure(bg=self.palette.bg)
        self.entry.configure(bg=self.palette.bg, fg=self.palette.ink, insertbackground=self.palette.ink)
        self.placeholder.configure(bg=self.palette.bg, fg=self.palette.placeholder)
        self.divider.configure(bg=self.palette.border)
        self.toolbar.configure(bg=self.palette.bg)
        if self.choice_menu:
            self.choice_menu.close(immediate=True)
        for button in (self.model_button, self.depth_button, self.category_button, self.send_button):
            button.palette = self.palette
            button.configure(bg=self.palette.bg)
        self._load_icons()
        self._draw_surface()
        self.refresh()
        LOG.info("Composer theme changed: theme=%s", name)

    def changed(self):
        if not hasattr(self, "send_button"):
            return
        self.refresh()
        if self._resize_id is None:
            self._resize_id = self.after_idle(self._resize_text)

    def _resize_text(self):
        self._resize_id = None
        lines = self.entry.count("1.0", "end-1c", "displaylines")
        count = max(2, min(6, (lines[0] if lines else 0)+1))
        if int(self.entry.cget("height")) != count:
            self.entry.configure(height=count)
        # Measure the requested rows directly. winfo_reqheight can still be
        # the old value during a font/width transition and clip the toolbar
        # into the Text on Windows embedded canvas windows.
        line_height=ui_font(self).metrics("linespace")
        toolbar_height=max(int(button.cget("height")) for button in
                           (self.model_button,self.depth_button,self.category_button,self.send_button))
        height=count*line_height+8+20+toolbar_height+30
        self.configure(height=height)
        signature=(count,line_height,toolbar_height,height,self.winfo_width())
        if signature!=getattr(self,"_layout_signature",None):
            self._layout_signature=signature
            LOG.debug("Composer layout measured: rows=%s line_px=%s toolbar_px=%s height_px=%s width_px=%s",
                      *signature)
        self.body.lift()
        self.entry.lift()
        self.toolbar.lift()
        self._place_placeholder()
        self._draw_surface()

    def _fit(self, event):
        self.itemconfigure(self.window, width=max(1, event.width-36))
        reserved = self.depth_button.winfo_reqwidth()+self.category_button.winfo_reqwidth()+self.send_button.winfo_reqwidth()+82
        self.model_button.configure(width=max(130, min(350, event.width-reserved)))
        self.changed()
        self._draw_surface()

    def _draw_surface(self):
        BG, MUTED, BORDER, INK, SUBTLE = self.palette.base
        w, h = self.winfo_width(), self.winfo_height()
        signature = (w, h, self.palette, self.focused)
        if signature == getattr(self, "_surface_signature", None):
            return
        self._surface_signature = signature
        self.delete("surface")
        rounded(self, (2, 4, w-2, h-1), 28, fill=self.palette.shadow, outline="", tags="surface")
        rounded(self, (2, 1, w-2, h-4), 28, fill=BG,
                outline=self.palette.focus if self.focused else BORDER, width=2, tags="surface")
        self.tag_lower("surface")

    def _focus(self, value):
        self.focused = value
        self._draw_surface()

    def _rotate_placeholder(self):
        self._placeholder_id = None
        phrases = ("描述你想完成的目标…", "说说你希望得到什么成果…", "补充你的要求，一起完善方案…")
        if not self.entry.get("1.0", "end-1c"):
            self._placeholder_index = (self._placeholder_index+1) % len(phrases)
            self.placeholder.configure(text=phrases[self._placeholder_index])
        self._placeholder_id = self.after(3200, self._rotate_placeholder)

    def refresh(self):
        if not hasattr(self, "send_button"):
            return
        locked = self.app._conversation_locked()
        text = self.entry.get("1.0", "end-1c")
        self.send_button.stop = locked
        self.send_button.text = "停止生成" if locked else "发送消息"
        self.send_button.command = self.app.cancel_active_request if locked else self.app.send_conversation_message
        self.send_button.configure(state="normal" if locked or text.strip() else "disabled")
        self.model_button.configure(state="disabled" if locked else "normal")
        for button in (self.depth_button, self.category_button):
            button.configure(state="disabled" if locked else "normal")
        self.depth_button.selection_value = self.app.thinking_level_var.get()
        self.category_button.selection_value = self.app.category_var.get()
        if text:
            self.placeholder.place_forget()
        else:
            self._place_placeholder()
        model = find_model(self.app.api_model_var.get())
        self.model_button.text = model.name if model else self.app.api_model_var.get().strip() or "选择模型"
        self.model_button.icon = self.icons.get(model.provider if model else self.app.provider_var.get())
        effort = self.app.preference_vars["reasoning_effort"].get()
        self.model_button.level = EFFORTS.index(effort) if effort in EFFORTS else -1
        self.model_button._draw()
        if self.picker:
            if locked:
                self.picker.close()
            else:
                self.picker.sync_selection()

    def _place_placeholder(self):
        if not self.entry.get("1.0", "end-1c"):
            # Use the actual first line box, sharing the Text baseline. Label
            # has no own padding and uses the same xterm pointer as the Text.
            line = self.entry.dlineinfo("1.0")
            if line:
                x, y, _width, height, _baseline = line
                self.placeholder.place(in_=self.entry, bordermode="outside", x=x+3, y=y, width=max(1,self.entry.winfo_width()-x-6),height=height)
                self.placeholder.lift()
        else:
            self.placeholder.place_forget()

    def toggle_choices(self, kind):
        from .interaction_ui import ChoiceMenu
        if self.app._conversation_locked():
            return
        previous = getattr(self.choice_menu,"kind",None)
        if self.choice_menu:
            self.choice_menu.close(immediate=True)
            if previous == kind:
                return
        anchor = self.depth_button if kind == "depth" else self.category_button
        if kind == "depth":
            items = list(self.app._thinking_labels.items())
            selected = self.app.thinking_level_var.get()
        else:
            items = [(label,label) for label in self.app.category_by_label]
            selected = self.app.category_var.get()
        def choose(key):
            if kind == "depth":
                self.app.thinking_level_display_var.set(self.app._thinking_labels[key])
                self.app._on_thinking_level_selected()
            else:
                self.app.category_var.set(key)
                self.app._on_category_selected()
            LOG.info("Composer task setting selected: kind=%s value=%s",kind,key)
            self.refresh()
        def closed():
            self.choice_menu = None
            anchor.expanded = False
            anchor._draw()
        self.choice_menu = ChoiceMenu(self.app,anchor,anchor.text,items,selected,choose,closed)
        self.choice_menu.kind = kind
        anchor.expanded = True
        anchor._draw()

    def toggle_picker(self):
        if self.picker:
            self.picker.close()
        elif not self.app._conversation_locked():
            if self._cached_picker is not None:
                self.picker = self._cached_picker
                self.picker.reopen()
            else:
                self.picker = ModelPicker(self)
                self._cached_picker = self.picker
        self.model_button.expanded = self.picker is not None
        self.model_button._draw()

    def choose_model(self, model):
        if self.app._conversation_locked():
            return
        app = self.app
        confirmed, connection = app._model_settings_confirmed(), app._connection_snapshot()
        # A custom gateway may host several model families under one service.
        # Fetched IDs carry their source service so the matching profile wins.
        # Legacy choices without a source keep the official preset behavior.
        host = (urlsplit(app.api_base_var.get()).hostname or "").lower()
        official = {urlsplit(p["base_url"]).hostname for p in PROVIDER_PRESETS.values()}
        switched = bool(model.service_provider and model.service_provider != app.provider_var.get())
        if switched:
            app.provider_var.set(model.service_provider)
            confirmed, connection = app._model_settings_confirmed(), app._connection_snapshot()
        elif not model.service_provider and model.provider in PROVIDER_PRESETS and (host in official or not host):
            if app.provider_var.get() != model.provider:
                app.provider_var.set(model.provider)
        if app.api_model_var.get().strip() != model.id or app.preference_vars["reasoning_effort"].get() not in EFFORTS:
            app.api_model_var.set(model.id)
            app.preference_vars["reasoning_effort"].set(model.default_effort)
            LOG.info("Composer model selected: provider=%s model=%s", model.provider, model.id)
            self._finish_choice(confirmed, connection)
        elif switched:
            self._finish_choice(confirmed, connection)
        self.refresh()

    def choose_effort(self, effort):
        if not self.app._conversation_locked() and effort in EFFORTS:
            if self.app.preference_vars["reasoning_effort"].get() != effort:
                confirmed, connection = self.app._model_settings_confirmed(), self.app._connection_snapshot()
                self.app.preference_vars["reasoning_effort"].set(effort)
                LOG.info("Composer thinking effort selected: model=%s effort=%s", self.app.api_model_var.get(), effort)
                self._finish_choice(confirmed, connection)
            self.refresh()

    def _finish_choice(self, confirmed, connection):
        app = self.app
        if confirmed and app._connection_snapshot() == connection:
            if app.save_settings(model_only=True, confirm_model=True):
                app._confirmed_connection_state = app._generation_snapshot()
                app._refresh_model_confirmation()
                app._refresh_primary_action()
                app.status_var.set("模型选择已应用并保存。")
                LOG.info("Composer choice applied on confirmed interface: model=%s effort=%s",
                         app.api_model_var.get(), app.preference_vars["reasoning_effort"].get())
        elif not app._model_settings_confirmed():
            app.status_var.set("请在右上角设置中配置当前模型接口并确认，然后继续对话。")
            LOG.info("Composer choice awaits interface confirmation in settings")

    def discard_picker(self):
        if self._cached_picker is not None:
            self._cached_picker.close()
            self._cached_picker.window.destroy()
            self._cached_picker = None

    def _destroyed(self, event):
        if event.widget is not self:
            return
        self.discard_picker()
        if self.choice_menu:
            self.choice_menu.close(immediate=True)
        for timer in (self._resize_id, self._placeholder_id):
            if timer:
                self.after_cancel(timer)
        for variable, trace in self._traces:
            variable.trace_remove("write", trace)


class ModelPicker:
    def __init__(self, composer):
        self.composer, self.app = composer, composer.app
        self.palette = composer.palette
        BG, MUTED, BORDER, INK, SUBTLE = self.palette.base
        self.root = self.app.root
        self.window = tk.Toplevel(self.root)
        self.window._promptsmith_font_scale = 1.0
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.transient(self.root)
        self.window.configure(bg=self.composer.cget("bg"))
        self.models = self.app.available_picker_models()
        current = find_model(self.app.api_model_var.get())
        self.provider = current.provider if current else "custom" if self.app.api_model_var.get().strip() else "DeepSeek"
        self.providers = tuple(p for p in (*PROVIDERS, "custom") if any(m.provider == p for m in self.models))
        if self.providers and self.provider not in self.providers:
            self.provider = self.providers[0]
        self.query = tk.StringVar(master=self.window)
        self.rows = ()
        self.row_widgets = []
        self.provider_buttons, self.effort_buttons = {}, {}
        self._closed = False
        self._focus_after = None
        self.surface = tk.Canvas(self.window, bg=self.composer.cget("bg"), highlightthickness=0)
        self.surface.pack(fill="both", expand=True)
        frame = tk.Frame(self.surface, bg=BG)
        frame_window = self.surface.create_window(6, 6, window=frame, anchor="nw")
        def fit_surface(event):
            self.surface.delete("surface")
            rounded(self.surface, (1, 1, event.width-1, event.height-1), 12,
                    fill=BG, outline=BORDER, tags="surface")
            self.surface.tag_lower("surface")
            self.surface.itemconfigure(frame_window, width=max(1, event.width-12), height=max(1, event.height-12))
        self.surface.bind("<Configure>", fit_surface)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        self.rail_canvas = tk.Canvas(frame, bg=MUTED, width=54, height=200, highlightthickness=0)
        self.rail_canvas.grid(row=0, column=0, sticky="ns")
        rail = tk.Frame(self.rail_canvas, bg=MUTED, width=54)
        self.rail_canvas.create_window(0, 0, window=rail, anchor="nw", width=54)
        rail.bind("<Configure>", lambda _e: self.rail_canvas.configure(scrollregion=self.rail_canvas.bbox("all")))
        self.provider_tip = tk.Label(frame, bg=INK, fg=BG, padx=8, pady=4, font=ui_font(self.window, 9))
        for provider in self.providers:
            image = composer.icons.get(provider)
            button = GlyphButton(rail, text="◇", provider=True, width=42, height=42, bg=MUTED,
                                 palette=self.palette, command=lambda p=provider: self.select_provider(p))
            button.icon = image
            button.pack(padx=6, pady=(7, 0))
            button.bind("<Up>", lambda _e, p=provider: self._move_provider(p, -1))
            button.bind("<Down>", lambda _e, p=provider: self._move_provider(p, 1))
            button.bind("<Enter>", lambda _e, p=provider, b=button: self._show_provider_tip(p, b))
            button.bind("<Leave>", lambda _e: self.provider_tip.place_forget())
            button.bind("<MouseWheel>", self._rail_wheel)
            self.provider_buttons[provider] = button
        right = tk.Frame(frame, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)
        search = tk.Frame(right, bg=MUTED)
        search.grid(row=0, column=0, sticky="ew")
        magnifier = tk.Canvas(search, bg=MUTED, width=22, height=22, highlightthickness=0)
        magnifier.create_oval(4, 3, 13, 12, outline=SUBTLE, width=1.5)
        magnifier.create_line(12, 11, 17, 16, fill=SUBTLE, width=1.5)
        magnifier.pack(side="left", padx=(10, 3))
        self.search = tk.Entry(search, textvariable=self.query, bg=MUTED, fg=INK,
                               relief="flat", highlightthickness=0, font=ui_font(self.window, 11))
        self.search.pack(side="left", fill="x", expand=True, pady=10)
        self.search_hint = tk.Label(search, text="搜索模型", fg=SUBTLE, bg=MUTED, font=ui_font(self.window, 11))
        self.search_hint.place(x=38, y=11)
        self.search_hint.bind("<Button-1>", lambda _e: self.search.focus_set())
        self.clear_button = tk.Button(search, text="×", command=lambda: self.query.set(""),
                                      bg=MUTED, fg=SUBTLE, relief="flat", bd=0, cursor="hand2",
                                      font=ui_font(self.window))
        self.clear_button.pack(side="right", padx=8)
        self.caption = tk.Label(right, fg=SUBTLE, bg=BG, anchor="w", font=ui_font(self.window, 10))
        self.caption.grid(row=1, column=0, sticky="ew", padx=14, pady=(8, 4))
        self.canvas = tk.Canvas(right, bg=BG, highlightthickness=0)
        self.canvas.grid(row=2, column=0, sticky="nsew", padx=(6, 0), pady=(0, 6))
        self.scroll = SlimScrollbar(right, self.palette, self.canvas.yview)
        self.scroll.grid(row=2, column=1, sticky="ns", padx=(0, 2))
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.list_frame = tk.Frame(self.canvas, bg=BG)
        self.list_window = self.canvas.create_window(0, 0, window=self.list_frame, anchor="nw")
        self.canvas.bind("<Configure>", self._fit_list)
        self.list_frame.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        footer = tk.Frame(frame, bg=BG)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        tk.Frame(footer, height=1, bg=BORDER).pack(fill="x")
        track = tk.Frame(footer, bg=BG)
        track.pack(fill="x", padx=12, pady=(10, 5))
        self.effort_meter = tk.Canvas(track, bg=BG, width=22, height=22, highlightthickness=0)
        self.effort_meter.pack(side="left", padx=(0, 5))
        tk.Label(track, text="思考强度", bg=BG, fg=SUBTLE, font=ui_font(self.window, 10)).pack(side="left", padx=(0, 8))
        track_canvas = tk.Canvas(track, bg=BG, highlightthickness=0, height=38, width=270)
        track_canvas.pack(side="left", fill="x", expand=True)
        steps = tk.Frame(track_canvas, bg=MUTED)
        steps_window = track_canvas.create_window(4, 4, window=steps, anchor="nw")
        def fit_track(event):
            track_canvas.delete("track")
            rounded(track_canvas, (1, 1, event.width-1, event.height-1), 19,
                    fill=MUTED, outline=BORDER, tags="track")
            track_canvas.tag_lower("track")
            track_canvas.itemconfigure(steps_window, width=max(1, event.width-8), height=30)
            for button in self.effort_buttons.values():
                button.configure(width=max(1, (event.width-8)//4))
        track_canvas.bind("<Configure>", fit_track)
        for effort in EFFORTS:
            button = GlyphButton(steps, text=EFFORT_LABELS[effort], bg=MUTED, height=30, width=60, palette=self.palette,
                                 choice=True, command=lambda e=effort: composer.choose_effort(e))
            button.pack(side="left", fill="x", expand=True)
            button.bind("<Right>", lambda _e, e=effort: self._move_effort(e, 1))
            button.bind("<Left>", lambda _e, e=effort: self._move_effort(e, -1))
            button.bind("<Home>", lambda _e: self._set_effort("low"))
            button.bind("<End>", lambda _e: self._set_effort("max"))
            self.effort_buttons[effort] = button
        self.note = tk.Label(footer, bg=BG, fg=SUBTLE, anchor="w", justify="left", font=ui_font(self.window, 10))
        self.note.pack(fill="x", padx=14, pady=(0, 10))
        self.query.trace_add("write", lambda *_a: self.render())
        self.window.bind("<Escape>", lambda _e: self.close())
        self.search.bind("<Down>", lambda _e: self._focus_row(0))
        self.search.bind("<Return>", lambda _e: self._select_row(0))
        self.window.bind("<FocusOut>", self._focus_out, add="+")
        self._outside_binding = self.root.bind("<Button-1>", self._outside, add="+")
        self.render()
        self._position()
        self.window.deiconify()
        self.window.lift()
        self.search.focus_set()
        LOG.debug("Model picker opened: provider=%s models=%s font_scale=%.2f name_pt=%s description_pt=%s effort_pt=%s",
                  self.provider, len(self.models), self.window._promptsmith_font_scale,
                  ui_font(self.window, 11, "bold").actual("size"),
                  ui_font(self.window, 10).actual("size"), ui_font(self.window, 11).actual("size"))

    def _position(self, *, flush=True):
        if flush:
            self.root.update_idletasks()
        scale = max(1, float(self.root.tk.call("tk", "scaling"))/(96/72))
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w = min(round(420*scale), sw-32)
        h = min(round(370*scale), max(280, self.root.winfo_height()-75), sh-100)
        x = min(max(16, self.composer.model_button.winfo_rootx()), sw-w-16)
        y = min(max(16, self.composer.model_button.winfo_rooty()-h-10), sh-h-50)
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.note.configure(wraplength=w-28)

    def select_provider(self, provider):
        self.provider = provider
        if self.query.get():
            self.query.set("")
        self.render()
        LOG.debug("Model picker category: provider=%s", provider)

    def render(self):
        BG, MUTED, BORDER, INK, SUBTLE = self.palette.base
        if self._closed:
            return
        query = self.query.get()
        signature = (self.provider, query, self.models)
        if signature == getattr(self, "_render_signature", None):
            self.sync_selection()
            return
        self._render_signature = signature
        self._selection_signature = None
        self.search_hint.place_forget() if query else self.search_hint.place(x=38, y=11)
        self.clear_button.configure(state="normal" if query else "disabled")
        self.rows = search_models(self.models, self.provider, query)
        self.caption.configure(text=f"{len(self.rows)} 个结果" if query.strip() else PROVIDER_LABELS[self.provider])
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.row_widgets = []
        for index, model in enumerate(self.rows):
            name_font = ui_font(self.window, 11, "bold")
            description_font = ui_font(self.window, 10)
            height = name_font.metrics("linespace")+description_font.metrics("linespace")+21
            row = tk.Canvas(self.list_frame, bg=BG, highlightthickness=0, takefocus=True,
                            cursor="hand2", height=height)
            row.pack(fill="x", padx=3, pady=2)
            content = tk.Frame(row, bg=BG)
            content.columnconfigure(1, weight=1)
            row._content = content
            row._content_window = row.create_window(12, 9, window=content, anchor="nw")
            row._search_icon = bool(query.strip() and model.provider in self.composer.icons)
            if query.strip() and model.provider in self.composer.icons:
                tk.Label(content, image=self.composer.icons[model.provider], bg=BG).grid(row=0, column=0, rowspan=2, padx=(0, 8))
            name = tk.Label(content, text=model.name, font=name_font, bg=BG, fg=INK, anchor="w", bd=0, padx=0, pady=0)
            name.grid(row=0, column=1, sticky="w")
            selected = tk.Canvas(content, width=20, height=20, highlightthickness=0, bg=BG)
            selected.create_image(10, 10, image=self.composer.check_icon, tags="check")
            selected.grid(row=0, column=2, padx=4)
            chips = tk.Canvas(content, bg=BG, highlightthickness=0, width=52 if model.image else 30, height=24)
            chips.grid(row=0, column=3, rowspan=2, sticky="e", padx=(5, 0))
            row._chips = chips
            row._image_capability = model.image
            row._reasoning_capability = model.reasoning
            row._model_service = model.service_provider
            row._name = name
            row._full_name = model.name
            description = tk.Label(content, text=model.description, font=description_font, bg=BG,
                                    fg=SUBTLE, anchor="w", bd=0, padx=0, pady=0)
            description.grid(row=1, column=1, columnspan=2, sticky="w", pady=(3, 0))
            row._model_id = model.id
            row._check = selected
            row._description = description
            row._full_description = model.description
            row.bind("<Configure>", lambda _e, r=row: self._fit_row(r))
            for child in (row, content, *content.winfo_children()):
                child.bind("<Button-1>", lambda _e, m=model: self.composer.choose_model(m))
                child.bind("<MouseWheel>", self._wheel)
                child.bind("<Enter>", lambda _e, r=row: self._paint_row(r, True))
                child.bind("<Leave>", lambda _e, r=row: self._paint_row(r, False))
            row.bind("<Return>", lambda _e, m=model: self.composer.choose_model(m) or "break")
            row.bind("<space>", lambda _e, m=model: self.composer.choose_model(m) or "break")
            row.bind("<Down>", lambda _e, i=index: self._focus_row(i+1))
            row.bind("<Up>", lambda _e, i=index: self._focus_row(i-1))
            row.bind("<Home>", lambda _e: self._focus_row(0))
            row.bind("<End>", lambda _e: self._focus_row(len(self.rows)-1))
            row.bind("<FocusIn>", lambda _e, r=row: self._paint_row(r, True))
            row.bind("<FocusOut>", lambda _e, r=row: self._paint_row(r, False))
            self.row_widgets.append(row)
            chips.bind("<Enter>", lambda _e, r=row: self._show_capability_tip(r), add="+")
            chips.bind("<Leave>", lambda _e: self.provider_tip.place_forget(), add="+")
            for label in (name, description):
                label.bind("<Enter>", lambda _e, r=row: self._show_row_tip(r), add="+")
                label.bind("<Leave>", lambda _e: self.provider_tip.place_forget(), add="+")
        if not self.rows:
            tk.Label(self.list_frame, text="没有找到匹配的模型，请换个关键词。", bg=BG, fg=SUBTLE,
                     font=ui_font(self.window, 10), wraplength=260, pady=30).pack()
        self.canvas.yview_moveto(0)
        self.sync_selection()

    def _paint_row(self, row, hover=False):
        BG, MUTED, BORDER, INK, SUBTLE = self.palette.base
        selected = row._model_id == self.app.api_model_var.get().strip() and (not row._model_service or row._model_service == self.app.provider_var.get())
        color = MUTED if hover or selected else BG
        signature = (color, row.winfo_width(), row.winfo_height())
        if signature == getattr(row, "_paint_signature", None):
            return
        row._paint_signature = signature
        row.configure(bg=BG)
        row.delete("surface")
        rounded(row, (0, 0, row.winfo_width(), row.winfo_height()), 12, fill=color, outline="", tags="surface")
        row.tag_lower("surface")
        row._content.configure(bg=color)
        for child in row._content.winfo_children():
            if isinstance(child, (tk.Label, tk.Canvas)):
                child.configure(bg=color)
        chips = row._chips
        chips.configure(bg=color)
        chips.delete("all")
        if not row._reasoning_capability and not row._image_capability:
            return
        width = 52 if row._image_capability else 30
        rounded(chips, (1, 1, width-1, 23), 11, fill=color, outline=BORDER)
        violet = "#a78bfa" if self.composer.theme_name == "dark" else "#8b5cf6"
        teal = "#2dd4bf" if self.composer.theme_name == "dark" else "#14b8a6"
        # Compact brain and image outlines reproduce the capability pills;
        # Chinese tooltips name their meaning, without growing the row.
        chips.create_line(15, 6, 12, 5, 9, 7, 9, 10, 8, 12, 9, 15, 12, 17, 15, 16,
                          smooth=True, splinesteps=12, fill=violet, width=1)
        chips.create_line(15, 6, 18, 5, 20, 8, 20, 11, 21, 13, 19, 16, 17, 18, 15, 16,
                          smooth=True, splinesteps=12, fill=violet, width=1)
        chips.create_line(15, 6, 15, 17, fill=violet, width=1)
        chips.create_line(11, 9, 12, 11, 15, 12, fill=violet, width=1, smooth=True)
        chips.create_line(19, 10, 17, 11, 17, 14, fill=violet, width=1, smooth=True)
        if row._image_capability:
            rounded(chips, (31, 7, 43, 18), 2, fill="", outline=teal)
            chips.create_oval(34, 9, 36, 11, outline=teal)
            chips.create_line(33, 16, 37, 12, 41, 16, fill=teal, width=1)

    def sync_selection(self):
        BG, MUTED, BORDER, INK, SUBTLE = self.palette.base
        if self._closed:
            return
        current_id = self.app.api_model_var.get().strip()
        effort = self.app.preference_vars["reasoning_effort"].get()
        signature = (current_id, self.app.provider_var.get(), effort, self.provider, self.query.get())
        if signature == getattr(self, "_selection_signature", None):
            return
        self._selection_signature = signature
        for row in self.row_widgets:
            selected = row._model_id == current_id and (not row._model_service or row._model_service == self.app.provider_var.get())
            row._check.itemconfigure("check", state="normal" if selected else "hidden")
            self._paint_row(row)
        for provider, button in self.provider_buttons.items():
            button.selected = provider == self.provider and not self.query.get().strip()
            button._draw()
        level = EFFORTS.index(effort) if effort in EFFORTS else -1
        self.effort_meter.delete("all")
        for i in range(4):
            self.effort_meter.create_line(3+i*5, 17, 3+i*5, 17-(i+1)*3,
                                          width=3, fill=INK if i <= level else BORDER)
        for value, button in self.effort_buttons.items():
            button.selected = effort == value
            button._draw()
        self.note.configure(text=effort_note(find_model(current_id), effort))

    def _fit_list(self, event):
        self.canvas.itemconfigure(self.list_window, width=max(1, event.width))

    def _fit_row(self, row):
        width = max(1, row.winfo_width()-24)
        row.itemconfigure(row._content_window, width=width)
        reserve = (52 if row._image_capability else 30)+13
        if row._search_icon:
            reserve += 32
        if width != getattr(row, "_fit_width", None):
            row._fit_width = width
            for label, text, budget, font in ((row._name, row._full_name, width-reserve-22, ui_font(self.window, 11, "bold")),
                                             (row._description, row._full_description, width-reserve, ui_font(self.window, 10))):
                label.configure(text=clipped_text(font, text, budget))
        self._paint_row(row)

    def _wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _rail_wheel(self, event):
        self.rail_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        self.provider_tip.place_forget()
        return "break"

    def _focus_row(self, index):
        if self.row_widgets:
            row = self.row_widgets[index % len(self.row_widgets)]
            row.focus_set()
            total = max(1, self.list_frame.winfo_height())
            self.canvas.yview_moveto(row.winfo_y()/total)
        return "break"

    def _select_row(self, index):
        if self.rows:
            self.composer.choose_model(self.rows[index])
        return "break"

    def _move_provider(self, current, direction):
        provider = self.providers[(self.providers.index(current)+direction) % len(self.providers)]
        self.select_provider(provider)
        self.provider_buttons[provider].focus_set()
        total = max(1, self.rail_canvas.bbox("all")[3])
        self.rail_canvas.yview_moveto(self.provider_buttons[provider].winfo_y()/total)
        return "break"

    def _show_provider_tip(self, provider, button):
        self.provider_tip.configure(text=PROVIDER_LABELS[provider], wraplength=0)
        y = button.winfo_rooty()-self.provider_tip.master.winfo_rooty()
        self.provider_tip.place(x=52, y=max(0, y+6))
        self.provider_tip.lift()

    def _show_capability_tip(self, row):
        self.provider_tip.configure(text="推理 · 图像理解" if row._image_capability else "推理", wraplength=0)
        y = row.winfo_rooty()-self.provider_tip.master.winfo_rooty()+row.winfo_height()
        self.provider_tip.place(x=180, y=min(y, self.provider_tip.master.winfo_height()-25))
        self.provider_tip.lift()

    def _show_row_tip(self, row):
        self.provider_tip.configure(text=f"{row._full_name}\n{row._full_description}", wraplength=270, justify="left")
        self.provider_tip.update_idletasks()
        y = row.winfo_rooty()-self.provider_tip.master.winfo_rooty()+row.winfo_height()
        y = max(0, min(y, self.provider_tip.master.winfo_height()-self.provider_tip.winfo_reqheight()))
        self.provider_tip.place(x=64, y=y)
        self.provider_tip.lift()

    def _set_effort(self, effort):
        self.composer.choose_effort(effort)
        self.effort_buttons[effort].focus_set()
        return "break"

    def _move_effort(self, current, direction):
        return self._set_effort(EFFORTS[(EFFORTS.index(current)+direction) % 4])

    def _outside(self, event):
        for widget in (self.window, self.composer.model_button):
            if widget.winfo_rootx() <= event.x_root < widget.winfo_rootx()+widget.winfo_width() and widget.winfo_rooty() <= event.y_root < widget.winfo_rooty()+widget.winfo_height():
                return
        self.close()

    def _focus_out(self, _event):
        if not self._closed and self._focus_after is None:
            self._focus_after = self.window.after(100, self._check_focus)

    def _check_focus(self):
        self._focus_after = None
        if not self._closed:
            focus = self.root.focus_get()
            if focus is None or focus.winfo_toplevel() is not self.window:
                self.close()

    def reopen(self):
        started = time.perf_counter()
        self._closed = False
        self.models = self.app.available_picker_models()
        current = find_model(self.app.api_model_var.get())
        provider = current.provider if current else "custom"
        available = tuple(p for p in (*PROVIDERS, "custom") if any(m.provider == p for m in self.models))
        if available and provider not in available:
            provider = available[0]
        if available != self.providers:
            self._closed = True
            self.window.destroy()
            self.composer.picker = ModelPicker(self.composer)
            self.composer._cached_picker = self.composer.picker
            return
        self.provider = provider
        if self.query.get():
            self.query.set("")
        self.render()
        self._outside_binding = self.root.bind("<Button-1>", self._outside, add="+")
        self._position(flush=False)
        self.window.deiconify()
        self.window.lift()
        self.search.focus_set()
        LOG.debug("Model picker reused: models=%s elapsed_ms=%.2f", len(self.models), (time.perf_counter()-started)*1000)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.root.unbind("<Button-1>", self._outside_binding)
        if self._focus_after:
            self.window.after_cancel(self._focus_after)
            self._focus_after = None
        self.window.withdraw()
        self.composer.picker = None
        self.composer.model_button.expanded = False
        if self.composer.model_button.winfo_exists():
            self.composer.model_button._draw()
            self.composer.model_button.focus_set()
        LOG.debug("Model picker closed")
