from __future__ import annotations

import json
import logging
import os
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .runtime_log import RuntimeLog
from .typography import ui_font


LEVELS = {"全部": logging.DEBUG, "INFO 及以上": logging.INFO,
          "WARN 及以上": logging.WARNING, "ERROR 及以上": logging.ERROR,
          "CRITICAL": logging.CRITICAL}

# Keep severity readable at a glance on the dark console background.
LEVEL_COLORS = {
    logging.DEBUG: "#66b3ff",      # blue
    logging.INFO: "#f5f7fa",       # white
    logging.WARNING: "#ffd166",    # yellow
    logging.ERROR: "#ff6b6b",      # red
    logging.CRITICAL: "#ff3b30",   # bright red
}
LEVEL_NAMES = {logging.DEBUG: "DEBUG", logging.INFO: "INFO", logging.WARNING: "WARN",
               logging.ERROR: "ERROR", logging.CRITICAL: "CRITICAL"}


def load_debug_preference(path: Path) -> bool:
    try:
        if path.stat().st_size > 65536:
            raise ValueError("Settings file is too large")
        data = json.loads(path.read_text(encoding="utf-8"))
        return isinstance(data, dict) and data.get("debug_console_enabled") is True
    except FileNotFoundError:
        return False
    except (OSError, ValueError) as exc:
        logging.getLogger(__name__).warning("Cannot read debug console preference: %s", exc, exc_info=True)
        return False


def save_debug_preference(path: Path, enabled: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # This file stores only diagnostics UI preferences, never model credentials.
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"debug_console_enabled": enabled}) + "\n", encoding="utf-8")
    temporary.replace(path)


class DebugConsole:
    def __init__(self, parent: tk.Misc, logs: RuntimeLog, on_close):
        self.logs = logs
        self.on_close = on_close
        self.last_sequence = 0
        self.clear_sequence = 0
        self.after_id = None
        self.closed = False
        self.line_limit = 6000
        self.refresh_ms = 150
        self.enabled_levels = set(LEVEL_COLORS)
        self.entry_tags = {}
        self.window = tk.Toplevel(parent)
        self.window._promptsmith_font_scale = 1.0
        font = ui_font(self.window)
        style = ttk.Style(self.window)
        for name in ("TLabel", "TButton", "TCheckbutton", "TCombobox", "Muted.TLabel"):
            style.configure("DebugConsole."+name, font=font)
        self.window.title("Intext · Debug 控制台")
        from .branding import apply_window_icon
        apply_window_icon(self.window)
        width = min(1120, max(400, parent.winfo_screenwidth() - 80))
        height = min(640, max(300, parent.winfo_screenheight() - 140))
        self.window.geometry(f"{width}x{height}")
        self.window.minsize(min(600, width), min(320, height))
        self.window.protocol("WM_DELETE_WINDOW", on_close)
        shell = ttk.Frame(self.window, padding=12)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(shell)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(4, weight=1)
        self.legend = ttk.Frame(toolbar)
        self.legend.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 8))
        self.legend.grid_anchor("e")
        self.legend_buttons, self.legend_icons = {}, {}
        for level, color in LEVEL_COLORS.items():
            icons = []
            for fill in (color, "#7e858d"):
                icon = tk.PhotoImage(master=self.window, width=10, height=10)
                for y in range(10):
                    for x in range(10):
                        if (x - 4.5)**2 + (y - 4.5)**2 <= 20:
                            icon.put(fill, (x, y))
                icons.append(icon)
            self.legend_icons[level] = icons
            self.legend_buttons[level] = tk.Button(
                self.legend, text=LEVEL_NAMES[level]+" 0", image=icons[0], compound="left",
                font=font, background="#16191c", foreground="#f5f7fa",
                activebackground="#30363c", activeforeground="#f5f7fa", relief="flat",
                padx=6, pady=4, command=lambda level=level: self.toggle_level(level))
        self.legend.bind("<Configure>", self._layout_legend)
        self._layout_legend()
        ttk.Label(toolbar, text="日志级别", style="DebugConsole.TLabel").grid(row=1, column=0, padx=(0, 6))
        self.level_var = tk.StringVar(master=self.window, value="全部")
        self.level_combo = ttk.Combobox(toolbar, textvariable=self.level_var, values=(*LEVELS, "自定义"),
                                       state="readonly", width=15, font=font, style="DebugConsole.TCombobox",
                                       postcommand=self._prepare_level_popup)
        self.level_combo.grid(row=1, column=1, sticky="w")
        self.level_combo.bind("<<ComboboxSelected>>", lambda _event: self.rebuild())
        self.autoscroll_var = tk.BooleanVar(master=self.window, value=True)
        ttk.Checkbutton(toolbar, text="自动滚动", variable=self.autoscroll_var,
                        command=self._autoscroll_changed, style="DebugConsole.TCheckbutton").grid(
            row=1, column=2, padx=12)
        ttk.Button(toolbar, text="复制日志", command=self.copy, style="DebugConsole.TButton").grid(row=1, column=3)
        self.save_button = ttk.Button(toolbar, text="保存日志", command=self.save, style="DebugConsole.TButton")
        self.save_button.grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Button(toolbar, text="清空显示", command=self.clear, style="DebugConsole.TButton").grid(row=2, column=1,
                                                                   sticky="w", pady=(6, 0))
        self.directory_button = ttk.Button(toolbar, text="打开日志目录", command=self.open_directory, style="DebugConsole.TButton")
        self.directory_button.grid(
            row=2, column=2, columnspan=2, sticky="w", pady=(6, 0))
        self.count_var = tk.StringVar(master=self.window)
        ttk.Label(toolbar, textvariable=self.count_var, style="DebugConsole.Muted.TLabel").grid(
            row=2, column=4, sticky="e")
        area = ttk.Frame(shell)
        area.grid(row=1, column=0, sticky="nsew")
        area.columnconfigure(0, weight=1)
        area.rowconfigure(0, weight=1)
        self.text = tk.Text(area, wrap="none", state="disabled", font=font,
                            background="#16191c", foreground="#e2e6e8", insertbackground="#ffffff",
                            relief="flat", padx=8, pady=8)
        self.text.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(area, command=self.text.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(area, orient="horizontal", command=self.text.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        for level, color in LEVEL_COLORS.items():
            self.text.tag_configure(str(level), foreground=color)
        self.path_var = tk.StringVar(master=self.window, value="未保存")
        path = ttk.Label(shell, textvariable=self.path_var, style="DebugConsole.Muted.TLabel", wraplength=800)
        path.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        shell.bind("<Configure>", lambda e: path.configure(wraplength=max(200, e.width - 24)), add="+")
        self.rebuild()
        self.poll()
        logging.getLogger(__name__).debug("Debug console typography: font_scale=1.00 display_pt=%s window=%sx%s",
                                         ui_font(self.window).actual("size"), width, height)

    def _layout_legend(self, event=None):
        width = event.width if event else self.window.winfo_width()
        item_width = max(button.winfo_reqwidth() for button in self.legend_buttons.values()) + 6
        columns = max(1, min(5, width // item_width))
        for i, button in enumerate(self.legend_buttons.values()):
            button.grid(row=i // columns, column=i % columns, sticky="e", padx=3, pady=2)

    def _update_legend(self):
        counts = dict.fromkeys(LEVEL_COLORS, 0)
        for entry in self.logs.entries_after(self.clear_sequence):
            counts[self._severity(entry.level)] += 1
        for level, button in self.legend_buttons.items():
            shown = level in self.enabled_levels
            button.configure(text=f"{LEVEL_NAMES[level]} {counts[level]}",
                             foreground="#f5f7fa" if shown else "#7e858d",
                             image=self.legend_icons[level][0 if shown else 1])

    @staticmethod
    def _severity(level):
        return next((value for value in reversed(LEVEL_COLORS) if level >= value), logging.DEBUG)

    def toggle_level(self, level):
        if level in self.enabled_levels:
            self.enabled_levels.remove(level)
        else:
            self.enabled_levels.add(level)
        self.level_var.set("自定义")
        self.rebuild()
        logging.getLogger(__name__).debug("Debug severity visibility: level=%s visible=%s",
                                         LEVEL_NAMES[level], level in self.enabled_levels)

    def _autoscroll_changed(self):
        if self.autoscroll_var.get():
            self.text.see("end")

    def _view_state(self):
        self.window.update_idletasks()
        top, bottom = self.text.yview()
        index = self.text.index("@0,0 linestart")
        self.text.mark_set("debug_reading", index)
        self.text.mark_gravity("debug_reading", "left")
        tag = next((tag for tag in self.text.tag_names(index) if tag.startswith("entry-")), None)
        start = self.text.tag_ranges(tag)[0] if tag else index
        offset = int(index.split(".")[0]) - int(str(start).split(".")[0])
        ranges = self.text.tag_ranges(tag) if tag else ()
        rows = self.text.get(*ranges).count("\n") if ranges else 0
        pixels = self.text.count("1.0", "end", "ypixels")[0]
        before = self.text.count("1.0", index, "ypixels")
        return dict(follow=self.autoscroll_var.get() and bottom >= .999, tag=tag, offset=offset, rows=rows,
                    pixels=top*pixels - (before[0] if before else 0), left=self.text.xview()[0])

    def _restore_view(self, view):
        self.window.update_idletasks()
        if view["follow"]:
            self.text.see("end")
        else:
            ranges = self.text.tag_ranges(view["tag"]) if view["tag"] else ()
            rows = self.text.get(*ranges).count("\n") if ranges else 0
            offset = max(0, view["offset"] + rows - view["rows"])
            index = f"{ranges[0]} + {offset} lines" if ranges else "debug_reading"
            before = self.text.count("1.0", index, "ypixels")
            total = self.text.count("1.0", "end", "ypixels")[0]
            self.text.yview_moveto(((before[0] if before else 0) + view["pixels"])/max(1, total))
        self.text.xview_moveto(view["left"])

    def _prepare_level_popup(self):
        # The native combobox listbox does not inherit ttk's widget font.
        popup = self.window.tk.call("ttk::combobox::PopdownWindow", str(self.level_combo))
        self.window.tk.call(f"{popup}.f.l", "configure", "-font", str(ui_font(self.window)))

    def _append(self, entries, view=None) -> None:
        view = view or self._view_state()
        self.text.configure(state="normal")
        for entry in entries:
            severity = self._severity(entry.level)
            if severity in self.enabled_levels:
                tag = f"entry-{entry.sequence}"
                self.entry_tags[entry.sequence] = tag
                self.text.insert("end", entry.text + "\n", (str(severity), tag))
        cached = self.logs.entries_after(self.clear_sequence)
        oldest = cached[0].sequence if cached else self.last_sequence + 1
        retained = [tag for sequence, tag in self.entry_tags.items() if sequence >= oldest]
        if retained:
            self.text.delete("1.0", self.text.tag_ranges(retained[0])[0])
        else:
            self.text.delete("1.0", "end")
        line_count = int(self.text.index("end-1c").split(".", 1)[0])
        if line_count > self.line_limit:
            self.text.delete("1.0", f"{line_count - self.line_limit + 1}.0")
        for sequence, tag in list(self.entry_tags.items()):
            if sequence < oldest or not self.text.tag_ranges(tag):
                self.text.tag_delete(tag)
                self.entry_tags.pop(sequence)
        self.text.configure(state="disabled")
        self._update_legend()
        self._restore_view(view)

    def rebuild(self) -> None:
        view = self._view_state()
        minimum = LEVELS.get(self.level_var.get())
        if minimum is not None:
            self.enabled_levels = {level for level in LEVEL_COLORS if level >= minimum}
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for tag in self.entry_tags.values():
            self.text.tag_delete(tag)
        self.entry_tags.clear()
        self.text.configure(state="disabled")
        entries = self.logs.entries_after(self.clear_sequence)
        self._append(entries, view)
        self.last_sequence = entries[-1].sequence if entries else self.clear_sequence

    def apply_preferences(self, values) -> None:
        self.level_var.set(values["debug_level"])
        self.autoscroll_var.set(values["debug_autoscroll"])
        self.line_limit = values["debug_lines"]
        self.refresh_ms = values.get("debug_refresh_ms", 150)
        self.rebuild()

    def poll(self) -> None:
        if self.closed:
            return
        if self.after_id is not None:
            self.window.after_cancel(self.after_id)
            self.after_id = None
        entries = self.logs.entries_after(self.last_sequence)
        count = f"{len(self.logs.entries_after())} 条缓存日志"
        if self.logs.file_error:
            status = f"保存失败：{self.logs.file_error}"
        elif self.logs.path is not None:
            status = f"已保存 {self.logs.saved_sequence} 条：{self.logs.path}"
        else:
            status = "未保存"
        if entries or count != self.count_var.get() or status != self.path_var.get():
            view = self._view_state()
            self.count_var.set(count)
            self.path_var.set(status)
            self._append(entries, view)
            if entries:
                self.last_sequence = entries[-1].sequence
        self.directory_button.configure(state="normal" if self.logs.directory.is_dir() else "disabled")
        self.after_id = self.window.after(self.refresh_ms, self.poll)

    def save(self) -> None:
        try:
            self.logs.save()
        except OSError:
            pass  # RuntimeLog retains the traceback; poll shows the failure for retry.
        self.poll()

    def clear(self) -> None:
        entries = self.logs.entries_after()
        self.clear_sequence = entries[-1].sequence if entries else 0
        self.rebuild()

    def copy(self) -> None:
        self.window.clipboard_clear()
        self.window.clipboard_append(self.text.get("1.0", "end-1c"))

    def open_directory(self) -> None:
        try:
            os.startfile(self.logs.directory)
        except (OSError, AttributeError):
            logging.getLogger(__name__).exception("Cannot open log directory: %s", self.logs.directory)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.after_id is not None:
            self.window.after_cancel(self.after_id)
            self.after_id = None
        self.window.destroy()
