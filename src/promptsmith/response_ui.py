"""Tk recreation of the supplied prose/trace reply component."""
import logging
import math
import re
import time
import tkinter as tk
import unicodedata
from tkinter import ttk
from tkinter import font as tkfont

from .typography import ui_font, UI_SCALE
from .composer import GlyphButton, SlimScrollbar, THEMES

HERO_TEXT = "让我们一起把一个目标变成一份完整的提示词吧。"
PROMPT_SECTIONS = frozenset({"任务背景与目标", "使用对象、场景和范围", "已确认要求与硬约束", "工作步骤",
    "关键工作与依赖", "交付物与完成标准", "所选 Agent Skill 与任务用法", "当前所选的方法适配", "未决事项",
    "待决定建议（当前未采纳，不要求执行）", "使用时补充的后置事项", "材料清单与提供条件"})


def palette(theme):
    return ({"bg": "#171717", "fg": "#f4f4f5", "muted": "#a1a1aa", "bubble": "#272727", "line": "#333333", "pill": "#292929"}
            if theme == "dark" else
            {"bg": "#ffffff", "fg": "#18181b", "muted": "#85858e", "bubble": "#f4f4f5", "line": "#e8e8ec", "pill": "#f4f4f5"})


class ReplyButton(GlyphButton):
    """Themed reply action retaining invoke/state/text button contracts."""
    def __init__(self, parent, *, text, command, theme="light", state="normal"):
        font = ui_font(parent, 11)
        super().__init__(parent, text=text, command=command, choice=True, palette=THEMES[theme],
                         width=font.measure(text)+32, height=max(32, font.metrics("linespace")+12), state=state)

    def cget(self, key):
        return self.text if key == "text" else super().cget(key)

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            self.text = kw.pop("text")
            kw.setdefault("width", ui_font(self, 11).measure(self.text)+32)
        return super().configure(cnf, **kw)

    config = configure

    def apply_theme(self, theme):
        self.palette = THEMES[theme]
        self.configure(bg=self.palette.bg, width=ui_font(self, 11).measure(self.text)+32,
                       height=max(32, ui_font(self, 11).metrics("linespace")+12))

    def _draw(self, event=None):
        self.selected = str(self.cget("state")) != "disabled"
        super()._draw(event)


def cluster_boundary(text, end, final=False):
    """Keep combining marks, emoji modifiers, flag pairs and ZWJ together."""
    while end < len(text) and (unicodedata.combining(text[end]) or text[end] in "\ufe0e\ufe0f\u200d" or text[end-1] == "\u200d"
                              or 0x1f3fb <= ord(text[end]) <= 0x1f3ff):
        end += 1
    if end < len(text) and 0x1f1e6 <= ord(text[end-1]) <= 0x1f1ff and 0x1f1e6 <= ord(text[end]) <= 0x1f1ff:
        end += 1
    if end == len(text) and not final:
        # Retain an incomplete final joiner, allowing the next SSE chunk to
        # supply its joined code point before displaying it.
        if text.endswith("\u200d"):
            return max(0, end-2)
    return end


class AdaptiveWriter:
    """Incremental insertion; no full-string redraw or synchronous flush."""
    interval = 16

    def __init__(self, widget, on_drained=lambda: None):
        self.widget, self.on_drained = widget, on_drained
        self.pending = ""
        self.after = None
        self.finished = False
        self.closed = False
        self.last_newline = False
        self.last_cr = False
        self.frames = 0
        self.largest_chunk = 0

    def feed(self, text):
        normalized = []
        for char in text:
            if char == "\n" and self.last_cr:
                self.last_cr = False
                continue
            self.last_cr = char == "\r"
            char = "\n" if char == "\r" else char
            if char in " \t" and self.last_newline:
                continue
            if char == "\n" and self.last_newline:
                continue
            self.last_newline = char == "\n"
            normalized.append(char)
        self.pending += "".join(normalized)
        self.schedule()

    def schedule(self):
        if not self.closed and self.after is None:
            self.after = self.widget.after(self.interval, self.tick)

    def finish(self):
        self.finished = True
        self.schedule()

    def tick(self):
        self.after = None
        if self.closed or not self.widget.winfo_exists():
            return
        backlog = len(self.pending)
        if backlog:
            size = min(backlog, max(1, min(4096, math.ceil(backlog / 18))))
            size = cluster_boundary(self.pending, size, self.finished)
            if size:
                chunk, self.pending = self.pending[:size], self.pending[size:]
                follow = self.widget.yview()[1] >= .96
                self.widget.configure(state="normal")
                self.widget.insert("end", chunk)
                self.widget.configure(state="disabled")
                if follow:
                    self.widget.yview_moveto(1)
                self.frames += 1
                self.largest_chunk = max(self.largest_chunk, size)
        if self.pending:
            self.schedule()
        elif self.finished:
            self.on_drained()

    def close(self):
        self.closed = True
        if self.after is not None:
            self.widget.after_cancel(self.after)
            self.after = None


class MarkdownText(tk.Text):
    """Native selectable Markdown, including ATX, Setext and HTML headings."""
    def __init__(self, parent, text, *, theme="light", height=10, section_titles=()):
        colors = palette(theme)
        super().__init__(parent, height=height, wrap="word", relief="flat", bd=0, highlightthickness=0,
                         bg=colors["bg"], fg=colors["fg"], insertbackground=colors["fg"], font=ui_font(parent), padx=0, pady=5)
        for level in range(1, 7):
            self.tag_configure("h"+str(level), font=ui_font(parent, max(self._body_size(), self._body_size()+11-level*2), "bold"), spacing1=10, spacing3=6)
        self.tag_configure("bold", font=ui_font(parent, "body", "bold"))
        self.tag_configure("code", background=colors["pill"])
        self.tag_configure("quote", foreground=colors["muted"], lmargin1=12, lmargin2=12)
        self.section_titles = section_titles
        self.render(text)

    def _body_size(self):
        return round(int(self.tk.call("font", "actual", self.cget("font"), "-size"))/UI_SCALE)

    def inline(self, text, tags=()):
        for token in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
            if token.startswith("**") and token.endswith("**"):
                self.insert("end", token[2:-2], (*tags, "bold"))
            elif token.startswith("`") and token.endswith("`"):
                self.insert("end", token[1:-1], (*tags, "code"))
            else:
                self.insert("end", token, tags)

    def render(self, text):
        self.configure(state="normal")
        self.delete("1.0", "end")
        lines = text.replace("\r\n", "\n").splitlines()
        index, fenced = 0, False
        while index < len(lines):
            line = lines[index]
            if line.lstrip().startswith("```"):
                fenced = not fenced
                index += 1
                continue
            heading = None if fenced else re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
            html = None if fenced else re.match(r"^\s*<h([1-6])[^>]*>(.*?)</h\1>\s*$", line, re.I)
            setext = not fenced and index+1 < len(lines) and re.match(r"^\s{0,3}(=+|-+)\s*$", lines[index+1]) and line.strip()
            if heading:
                self.inline(heading[2], ("h"+str(len(heading[1])),))
            elif html:
                self.inline(html[2], ("h"+html[1],))
            elif setext:
                self.inline(line, ("h1" if lines[index+1].strip().startswith("=") else "h2",))
                index += 1
            elif not fenced and line in self.section_titles and (index == 0 or not lines[index-1].strip()):
                # Program-generated plain prompt sections retain their exact
                # copy/export text; hierarchy is a presentation-only tag.
                self.insert("end", line, "h2")
            elif fenced:
                self.insert("end", line, "code")
            else:
                self.inline(line.removeprefix("> "), ("quote",) if line.startswith("> ") else ())
            self.insert("end", "\n")
            index += 1
        self.configure(state="disabled")


class MessageShell(tk.Frame):
    def __init__(self, parent, title, *, theme="light", user=False):
        colors = palette(theme)
        super().__init__(parent, bg=colors["bg"])
        self.columnconfigure(0, weight=1)
        if user:
            row=tk.Frame(self,bg=colors["bg"])
            row.grid(row=0,column=0,sticky="e",padx=(90,0))
            self.actions=tk.Frame(row,bg=colors["bg"])
            canvas = tk.Canvas(row, highlightthickness=0, bg=colors["bg"], width=600, height=65)
            canvas.grid(row=0, column=1, sticky="e")
            self.body = tk.Frame(canvas, bg=colors["bubble"], padx=12, pady=10)
            self.body._reply_action_host=self.actions
            self.body._reply_wrap_limit = 700
            font = ui_font(parent)
            measure_font = font if hasattr(font, "measure") else tkfont.Font(parent, font=font)
            self._measure_font = measure_font
            window = canvas.create_window((12, 8), window=self.body, anchor="nw")
            def fit(_event=None):
                natural = max((measure_font.measure(line) for child in self.body.winfo_children()
                               if isinstance(child, tk.Label) for line in str(child.cget("text")).splitlines()), default=500) + 55
                action_width=self.actions.winfo_reqwidth()+12 if self.actions.winfo_children() else 0
                width = max(100, min(760, self.winfo_width()-95-action_width, natural))
                height = self.body.winfo_reqheight()+16
                canvas.configure(width=width, height=height)
                canvas.itemconfigure(window, width=width-24)
                for child in self.body.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(wraplength=max(50, width-55))
                canvas.delete("bubble")
                radius = 17
                points = [radius,0,width-radius,0,width,0,width,radius,width,height-radius,width,height,
                          width-radius,height,radius,height,0,height,0,height-radius,0,radius,0,0]
                canvas.create_polygon(points, smooth=True, fill=colors["bubble"], outline="", tags="bubble")
                canvas.tag_lower("bubble")
            self.bind("<Configure>", fit)
            self.body.bind("<Configure>", fit)
        else:
            self.body = tk.Frame(self, bg=colors["bg"], padx=6, pady=4)
            self.body.grid(row=0, column=0, sticky="ew", padx=(0, 45))
        self.body._reply_colors = {**colors, "bg": colors["bubble"] if user else colors["bg"]}
        if not user:
            tk.Label(self.body, text=title, bg=colors["bg"], fg=colors["muted"], font=ui_font(parent, 10), anchor="w").pack(fill="x", pady=(0, 8))


class ResponseTrace(tk.Frame):
    def __init__(self, parent, record, *, theme="light"):
        from .interaction_ui import ChevronButton, RevealFrame
        self.theme = theme
        self.colors = palette(theme)
        super().__init__(parent, bg=self.colors["bg"], padx=6, pady=6)
        self.record = record
        self.opened = False
        self._header_text = None
        self._has_thought = None
        self._indicator_after = None
        self._indicator_phase = 0
        self.started = time.monotonic()
        header_row = tk.Frame(self, bg=self.colors["bg"])
        header_row.pack(anchor="w")
        self.indicator = tk.Canvas(header_row, width=14, height=18, bg=self.colors["bg"], bd=0, highlightthickness=0)
        self.indicator.pack(side="left", padx=(0, 4))
        self.dots = [self.indicator.create_oval(1+x*4, 3+y*4, 3+x*4, 5+y*4, outline="", fill=self.colors["muted"])
                     for y in range(3) for x in range(3)]
        self.header = ChevronButton(header_row, "正在处理…", self.toggle, bg=self.colors["bg"],fg=self.colors["muted"],opened=self.opened)
        self.header.pack(side="left")
        self.channel = RevealFrame(self, bg=self.colors["bg"],opened=self.opened)
        self.channel.pack(fill="x", padx=(8, 0), pady=5)
        line = tk.Frame(self.channel.body, bg=self.colors["line"], width=1)
        line.pack(side="left", fill="y")
        inner = tk.Frame(self.channel.body, bg=self.colors["bg"], padx=10)
        inner.pack(side="left", fill="both", expand=True)
        self.thinking_button = ChevronButton(inner,"思考中…",self.toggle_thought,bg=self.colors["bg"],fg=self.colors["muted"],size=10)
        self.thinking_button.pack(fill="x")
        self.thought_frame = RevealFrame(inner,bg=self.colors["bg"])
        self.thought_frame.pack(fill="x", padx=(15, 0))
        self.thought_frame.body._promptsmith_font_scale = 1.0
        self.thought_frame.body.columnconfigure(0, weight=1)
        self.thought = tk.Text(self.thought_frame.body, height=7, wrap="word", state="disabled", relief="flat", bd=0, highlightthickness=0,
                               bg=self.colors["bg"], fg=self.colors["muted"], font=ui_font(self.thought_frame.body), spacing1=0, spacing3=0, pady=5)
        logging.getLogger(__name__).debug("Reasoning text typography: id=%s font_scale=1.00 display_pt=%s",
                                         record.get("id"), ui_font(self.thought_frame.body).actual("size"))
        self.thought.grid(row=0, column=0, sticky="ew")
        scroll = SlimScrollbar(self.thought_frame.body, THEMES[theme], command=self.thought.yview)
        scroll.grid(row=0, column=1, sticky="ns", padx=(3, 0))
        self.thought.configure(yscrollcommand=scroll.set)
        self._thought_wheel_remainder = 0
        self.thought.bind("<MouseWheel>", self.scroll_thought)
        self.thought.bind("<Button-4>", lambda e:self.scroll_thought(e,120))
        self.thought.bind("<Button-5>", lambda e:self.scroll_thought(e,-120))
        self.writer = AdaptiveWriter(self.thought, self.drained)
        self.pills = tk.Frame(inner, bg=self.colors["bg"])
        self.pills.pack(fill="x", pady=(6, 0))
        for label, value in record.get("activities", []):
            row = tk.Frame(self.pills, bg=self.colors["bg"])
            row.pack(fill="x", pady=4)
            icon = tk.Canvas(row, width=16, height=18, bg=self.colors["bg"], bd=0, highlightthickness=0)
            icon.pack(side="left", padx=(0, 7))
            ink = "#7c6df2"
            icon.create_rectangle(3, 3, 12, 14, outline=ink, width=1.2)
            icon.create_line(5, 6, 10, 6, fill=ink)
            icon.create_line(5, 9, 10, 9, fill=ink)
            icon.create_line(5, 12, 8, 12, fill=ink)
            tk.Label(row, text=label, bg=self.colors["bg"], fg=self.colors["fg"], font=ui_font(parent, 10)).pack(side="left")
            detail = tk.Label(row, text=str(value), bg=self.colors["pill"], fg=self.colors["muted"], font=ui_font(parent, 9), padx=7, pady=1, wraplength=420, justify="left")
            detail.pack(side="left", padx=8)
            row.bind("<Configure>", lambda event, label=detail: label.configure(wraplength=max(90, event.width-180)))
        self.note = tk.Label(inner, text="", bg=self.colors["bg"], fg=self.colors["muted"], font=ui_font(parent, 10), anchor="w", wraplength=650)
        self.note.pack(fill="x", pady=3)
        if record.get("reasoning"):
            self.writer.feed(record["reasoning"])
        if record.get("status") != "working":
            self.finish()
            self.channel.configure(height=1)
        self.update_status()
        self.animate_indicator()
        self.bind("<Destroy>", self.destroyed, add="+")

    def animate_indicator(self):
        self._indicator_after = None
        working = self.record.get("status") == "working"
        for i, dot in enumerate(self.dots):
            self.indicator.itemconfigure(dot, fill=self.colors["muted"] if not working or (i+self._indicator_phase)%9 < 3 else self.colors["line"])
        if working:
            self._indicator_phase += 1
            self._indicator_after = self.after(80, self.animate_indicator)

    def toggle(self):
        self.opened = not self.opened
        self.channel.reveal(self.opened)
        self.header.set_open(self.opened)
        self.update_status()

    def scroll_thought(self, event, delta=None):
        delta = int(event.delta if delta is None else delta)
        if delta*self._thought_wheel_remainder<0:
            self._thought_wheel_remainder=0
        self._thought_wheel_remainder+=delta
        steps=int(self._thought_wheel_remainder/120)
        self._thought_wheel_remainder-=steps*120
        if steps:
            self.thought.yview_scroll(-steps*3,"units")
        # A dedicated bounded reading surface owns its wheel, even at edges.
        return "break"

    def apply_theme(self, theme):
        if theme == self.theme:
            return
        old, new = self.colors, palette(theme)
        mapping = {old[key]: new[key] for key in old}
        def visit(widget):
            for option in ("bg", "fg", "activebackground", "activeforeground"):
                if option in widget.keys() and widget.cget(option) in mapping:
                    widget.configure(**{option: mapping[widget.cget(option)]})
            if isinstance(widget, SlimScrollbar):
                widget.palette = THEMES[theme]
                widget._draw()
            from .interaction_ui import ChevronButton
            if isinstance(widget, ChevronButton):
                widget.configure(fg=new["muted"])
            for child in widget.winfo_children():
                visit(child)
        visit(self)
        self.colors, self.theme = new, theme

    def toggle_thought(self):
        self.thought_frame.reveal(not self.thought_frame.opened)
        self.thinking_button.set_open(self.thought_frame.opened)

    def update_status(self):
        has_thought = bool(str(self.record.get("reasoning") or "").strip())
        if has_thought != self._has_thought:
            if has_thought:
                self.thinking_button.pack(fill="x", before=self.pills)
                self.thought_frame.pack(fill="x", padx=(15, 0), before=self.pills)
            else:
                focus = self.focus_get()
                if focus is self.thinking_button or (focus and str(focus).startswith(str(self.thought_frame) + ".")):
                    self.header.focus_set()
                self.thinking_button.pack_forget()
                self.thought_frame.pack_forget()
            self._has_thought = has_thought
            logging.getLogger(__name__).debug("Reasoning visibility changed: id=%s visible=%s",
                                             self.record.get("id"), has_thought)
        status = self.record.get("status")
        label = {"working": "正在处理…", "done": "已完成", "failed": "处理未完成", "cancelled": "已取消"}.get(status, "已完成")
        text = f"{label} · {self.record.get('elapsed', 0):.1f} 秒"
        if text != self._header_text:
            self.header.configure(text=text)
            self._header_text = text

    def finish(self):
        self.writer.finish()
        self.update_status()
        if self.record.get("status") == "failed":
            self.note.configure(text=self.record.get("error", "本次输出未完成。已有内容保留，可以重试。"))
        elif self.record.get("status") == "cancelled":
            self.thinking_button.configure(text="思考内容（已取消）")
            self.note.configure(text="已取消本次生成，已有内容保留。可以重试或继续其它操作。")

    def drained(self):
        self.thinking_button.configure(text="思考内容" if self.record.get("reasoning") else "本次服务未返回可展示的思考内容")
        logging.getLogger(__name__).debug("Reasoning animation drained: id=%s frames=%s largest_chunk=%s", self.record.get("id"), self.writer.frames, self.writer.largest_chunk)

    def destroyed(self, event):
        if event.widget is self:
            self.close()

    def close(self):
        self.writer.close()
        if self._indicator_after is not None:
            self.after_cancel(self._indicator_after)
            self._indicator_after = None
