"""Native replicas of the supplied motion dropdown and sheen pill controls.

All raster layers are created in memory. Typography stays native and crisp.
"""
import logging
import math
import time
import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter, ImageTk

from .composer import GlyphButton, SlimScrollbar, THEMES, rounded
from .typography import ui_font
from .paths import resource_root

LOG = logging.getLogger(__name__)


def spring(t):
    # Damped spring: small overshoot like motion's bounce=.1/duration=.38.
    return 1 if t >= 1 else 1 - math.exp(-8*t) * math.cos(10*t)


class Tween:
    def __init__(self, widget):
        self.widget, self.job = widget, None
        widget.bind("<Destroy>", self._destroy, add="+")

    def _destroy(self, event):
        if event.widget is self.widget:
            self.cancel()

    def cancel(self):
        if self.job is not None:
            try:
                self.widget.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None

    def start(self, update, done=lambda: None, *, duration=380, curve=spring):
        self.cancel()
        started = time.perf_counter()
        def tick():
            self.job = None
            if not self.widget.winfo_exists():
                return
            t = min(1, (time.perf_counter()-started)*1000/duration)
            update(curve(t))
            if t < 1:
                self.job = self.widget.after(16, tick)
            else:
                done()
        tick()


class RevealFrame(tk.Frame):
    """Clip content during a reversible height animation; no Text redraw."""
    def __init__(self, parent, *, bg, opened=True):
        super().__init__(parent, bg=bg, height=1)
        self.pack_propagate(False)
        self.body = tk.Frame(self, bg=bg)
        self.body.place(x=0,y=0,relwidth=1)
        self.opened = opened
        self.tween = Tween(self)
        self.body.bind("<Configure>", self._fit, add="+")

    def _fit(self, _event=None):
        if self.opened and self.tween.job is None:
            self.configure(height=max(1, self.body.winfo_reqheight()))

    def reveal(self, opened):
        self.opened = opened
        start = self.winfo_height() if self.winfo_manager() else 0
        end = max(1, self.body.winfo_reqheight()) if opened else 0
        # Height clips cannot overshoot zero. Use a symmetric cubic easing so
        # both directions retain visible intermediate frames for the duration.
        self.tween.start(lambda p: self.configure(height=max(1, round(start+(end-start)*p))),
                         curve=lambda t: 4*t*t*t if t<.5 else 1-(-2*t+2)**3/2)
        LOG.debug("Reply reveal animation: opened=%s height=%s duration_ms=380", opened, end)


class ChevronButton(tk.Canvas):
    def __init__(self, parent, text, command, *, bg, fg, opened=True, size=11):
        self.text, self.command = text, command
        self.ink, self.angle = fg, math.pi/2 if opened else 0
        self.font = ui_font(parent, size)
        super().__init__(parent, width=self.font.measure(text)+35, height=self.font.metrics("linespace")+10,
                         bg=bg, highlightthickness=0, takefocus=True, cursor="hand2")
        self.tween = Tween(self)
        self.bind("<Configure>", self.draw)
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Return>", lambda e: (command(), "break")[1])
        self.bind("<space>", lambda e: (command(), "break")[1])
        self.draw()

    def cget(self, key):
        return self.text if key == "text" else super().cget(key)

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            self.text = kw.pop("text")
            kw.setdefault("width", self.font.measure(self.text)+35)
        if "fg" in kw:
            self.ink = kw.pop("fg")
        result = super().configure(cnf, **kw)
        if hasattr(self, "font"):
            self.draw()
        return result
    config = configure

    def set_open(self, opened):
        start, end = self.angle, math.pi/2 if opened else 0
        self.tween.start(lambda p: self._angle(start+(end-start)*p))

    def _angle(self, value):
        self.angle = value
        self.draw()

    def draw(self, _event=None):
        self.delete("all")
        y = int(super().cget("height"))/2
        coords = []
        for x0, y0 in ((-3,-5), (2,0), (-3,5)):
            coords.extend((12+x0*math.cos(self.angle)-y0*math.sin(self.angle),
                           y+x0*math.sin(self.angle)+y0*math.cos(self.angle)))
        self.create_line(*coords, fill=self.ink, width=1.8, capstyle="round", joinstyle="round")
        self.create_text(29, y, text=self.text, anchor="w", font=self.font, fill=self.ink)


class GlassButton(GlyphButton):
    """SheenPillButton: veil, light band, rim wire and native label well."""
    def __init__(self, parent, *, text, command, palette, icon_name=None):
        self.amount = 0.
        self.images = {}
        self.icon_name = icon_name
        self._icon_image = None
        self._tip = None
        font = ui_font(parent, 11)
        size=max(44,font.metrics("linespace")+18)
        super().__init__(parent, text=text, command=command, palette=palette,
                         width=size if icon_name else font.measure(text)+38, height=size)
        self.tween = Tween(self)
        if icon_name:
            self._load_action_icon()
            self.bind("<Enter>",lambda _e:self._show_tip(),add="+")
            self.bind("<Leave>",lambda _e:self._hide_tip(),add="+")
            self.bind("<Destroy>",lambda _e:self._hide_tip(),add="+")

    def cget(self,key):
        return self.text if key=="text" else super().cget(key)

    def _load_action_icon(self):
        suffix="_dark.png" if self.palette == THEMES["dark"] else ".png"
        path=resource_root()/"resources/ui/action_icons"/(self.icon_name+suffix)
        size=round(22*max(1,float(self.tk.call("tk","scaling"))/(96/72)))
        try:
            with Image.open(path) as source:
                self._icon_image=ImageTk.PhotoImage(source.convert("RGBA").resize((size,size),Image.Resampling.LANCZOS),master=self)
            LOG.debug("Glass action icon loaded: icon=%s theme=%s size_px=%s",self.icon_name,suffix,size)
        except (OSError,ValueError):
            LOG.exception("Glass action icon unavailable: %s",path)

    def _show_tip(self):
        self._hide_tip()
        self._tip=tk.Toplevel(self)
        self._tip.withdraw()
        self._tip.overrideredirect(True)
        self._tip.configure(bg=self.palette.ink)
        tk.Label(self._tip,text=self.text,font=ui_font(self,10),bg=self.palette.ink,fg=self.palette.bg,
                 padx=8,pady=4).pack()
        self._tip.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty()-32}")
        self._tip.deiconify()

    def _hide_tip(self):
        if self._tip is not None:
            self._tip.destroy()
            self._tip=None

    def _hover(self, value):
        self.hover = value
        start, end = self.amount, float(value)
        self.tween.start(lambda p: self._transition(start+(end-start)*p), duration=250, curve=lambda t:t)

    def _transition(self, value):
        self.amount = value
        self._draw()

    def _draw(self, _event=None):
        if not hasattr(self, "amount"):
            return
        w, h = int(self.cget("width")), int(self.cget("height"))
        key = (w, h, self.palette, round(self.amount*12))
        if key not in self.images:
            scale = 2
            image = Image.new("RGBA", (w*scale,h*scale), self.palette.bg)
            dark = self.palette == THEMES["dark"]
            shadow = Image.new("RGBA", image.size)
            ImageDraw.Draw(shadow).rounded_rectangle((6,12,w*scale-6,h*scale-2), radius=h,
                fill=(0,0,0,90 if dark else 45))
            image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(4)))
            draw = ImageDraw.Draw(image)
            inset = 5-self.amount*1.5  # hover scale 1.02, within the allocated hit target
            box = (inset,3,w*scale-inset,h*scale-9)
            draw.rounded_rectangle(box, radius=h, fill=self.palette.muted, outline=self.palette.border, width=2)
            light = Image.new("RGBA", image.size)
            ld = ImageDraw.Draw(light)
            ld.arc((inset+1,4,h*2-12,h*scale-10), 115,270, fill=(255,255,255,round(150+70*self.amount)), width=3)
            ld.arc((w*scale-h*2+12,4,w*scale-inset-1,h*scale-10), -65,90,
                   fill=(255,255,255,round(150+70*self.amount)), width=3)
            image = Image.alpha_composite(image, light.filter(ImageFilter.GaussianBlur(.8)))
            ImageDraw.Draw(image).rounded_rectangle((9,7,w*scale-9,h*scale-14), radius=h,
                outline=(255,255,255,round((35 if dark else 160)+50*self.amount)), width=1)
            self.images[key] = ImageTk.PhotoImage(image.resize((w,h),Image.Resampling.LANCZOS), master=self)
            if len(self.images)>32:
                self.images = {key:self.images[key]}
        self.delete("all")
        self.create_image(w/2,h/2,image=self.images[key])
        ink = self.palette.subtle if self.cget("state")=="disabled" else self.palette.ink
        if self.icon_name:
            if self._icon_image is not None:
                self.create_image(w/2,h/2-2-self.amount*.5,image=self._icon_image)
            else:
                self.create_arc(w/2-8,h/2-10,w/2+8,h/2+6,start=40,extent=280,style="arc",outline=ink,width=2)
        else:
            self.create_text(w/2-6,h/2-2-self.amount*.5,text=self.text,font=ui_font(self,11),fill=ink)
            direction = -1 if self.expanded else 1
            self.create_line(w-23,h/2-4*direction,w-19,h/2,w-15,h/2-4*direction,fill=ink,width=1.5)
        if self.focused:
            rounded(self,(2,2,w-2,h-6),h/2,fill="",outline=self.palette.focus,width=2)


class AnchoredPanel:
    """Bounded transient popover with the supplied .38s entrance/exit spring."""
    def __init__(self, app, anchor, title, *, width=780, height=570, on_close=lambda:None):
        self.app, self.anchor, self.on_close = app, anchor, on_close
        self.closed = False
        self.progress = 0.
        self._shown = False
        self._show_id = None
        self.window = tk.Toplevel(app.root)
        win = self.window
        win.withdraw()
        win.overrideredirect(True)
        win.transient(app.root)
        colors = THEMES[app.preferences["composer_theme"]]
        self.colors = colors
        # Colour-key transparency combined with alpha and a resizing HWND can
        # expose a black backing surface during Windows composition. Keep a
        # theme-coloured backing and animate the shell inside a fixed HWND.
        win.configure(bg=colors.bg)
        shell=tk.Canvas(win,bg=colors.bg,highlightthickness=0)
        self.shell = shell
        shell.pack(fill="both",expand=True)
        self.surface = tk.Frame(shell, bg=colors.bg, padx=14,pady=10)
        self.surface_id=shell.create_window(9,9,window=self.surface,anchor="nw")
        shell.bind("<Configure>",lambda _e:self._draw_shell())
        self.surface.columnconfigure(0,weight=1)
        self.surface.rowconfigure(1,weight=1)
        bar = tk.Frame(self.surface,bg=colors.bg)
        bar.grid(row=0,column=0,sticky="ew",pady=(0,8))
        tk.Label(bar,text=title,font=ui_font(win, "heading","bold"),bg=colors.bg,fg=colors.ink).pack(side="left")
        close = GlyphButton(bar,text="关闭",command=self.close,choice=True,palette=colors,
                            width=ui_font(win,11).measure("关闭")+24,height=ui_font(win,11).metrics("linespace")+10)
        close.pack(side="right")
        self.canvas = tk.Canvas(self.surface,bg=colors.bg,highlightthickness=0)
        self.canvas.grid(row=1,column=0,sticky="nsew")
        scroll=SlimScrollbar(self.surface,colors,self.canvas.yview)
        scroll.grid(row=1,column=1,sticky="ns")
        self.canvas.configure(yscrollcommand=scroll.set)
        self.body = tk.Frame(self.canvas,bg=colors.bg)
        self.item = self.canvas.create_window(0,0,window=self.body,anchor="nw")
        self.canvas.bind("<Configure>",lambda e:self.canvas.itemconfigure(self.item,width=e.width))
        self.body.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        win.bind("<MouseWheel>",self.wheel)
        win.bind("<Escape>",lambda e:(self.close(),"break")[1])
        self.outside_id = app.root.bind("<Button-1>",self.outside,add="+")
        self.root_geometry = self._root_geometry()
        self.move_id = app.root.bind("<Configure>",self.moved,add="+")
        self.width = min(width,max(260,app.root.winfo_width()-40))
        self.height = min(height,max(160,app.root.winfo_height()-90),win.winfo_screenheight()-80)
        self.x = max(0,min(anchor.winfo_rootx()+anchor.winfo_width()-self.width,win.winfo_screenwidth()-self.width-12))
        below = anchor.winfo_rooty()+anchor.winfo_height()+8
        self.y = below if below+self.height<=win.winfo_screenheight()-20 else max(20,anchor.winfo_rooty()-self.height-8)
        win.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
        win.attributes("-alpha",0.)
        self.tween = Tween(win)
        # Let the caller finish adding menu rows/table content before mapping.
        self._show_id = win.after_idle(self._show)
        LOG.debug("Workspace popover prepared: title=%s width=%s height=%s backing=%s native_size=fixed",
                  title,self.width,self.height,colors.bg)

    def _draw_shell(self):
        scale = .97+.03*self.progress
        dx,dy = self.width*(1-scale)/2,self.height*(1-scale)/2
        self.shell.delete("shell")
        rounded(self.shell,(dx+2,dy+4,self.width-dx-2,self.height-dy-1),18,
                fill=self.colors.shadow,outline="",tags="shell")
        rounded(self.shell,(dx+1,dy+1,self.width-dx-1,self.height-dy-5),16,
                fill=self.colors.bg,outline=self.colors.border,tags="shell")
        self.shell.tag_lower("shell")
        self.shell.coords(self.surface_id,dx+9,dy+9)
        self.shell.itemconfigure(self.surface_id,width=max(1,round(self.width-2*dx-18)),
                                 height=max(1,round(self.height-2*dy-22)))

    def _show(self):
        self._show_id = None
        if self.closed:
            return
        self.animate(0.)
        self.window.deiconify()
        # Flush mapping, layout and painting while fully invisible; otherwise
        # the first visible frame can contain an empty native surface.
        self.window.update_idletasks()
        if self.closed:
            return
        self.window.lift()
        self._shown = True
        self.tween.start(self.animate,lambda:LOG.debug("Workspace popover entrance finished"))
        LOG.info("Workspace popover opened: width=%s height=%s animation=fade_slide_shell_scale duration_ms=380",
                 self.width,self.height)

    def animate(self,p):
        self.progress = max(0,min(1.015,p))
        self._draw_shell()
        self.window.geometry(f"{self.width}x{self.height}+{self.x}+{self.y+round(-6*(1-self.progress))}")
        self.window.attributes("-alpha",min(1,self.progress))

    def wheel(self,e):
        widget=e.widget
        if isinstance(widget,(tk.Text,)):
            first,last=widget.yview()
            if (e.delta>0 and first>0) or (e.delta<0 and last<1):
                # Native class binding has already scrolled the Text.
                return "break"
        self.canvas.yview_scroll(-int(e.delta/120)*3,"units")
        return "break"

    def _root_geometry(self):
        root = self.app.root
        return (root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height())

    def moved(self,e):
        # Windows also sends Configure when stacking/exposure changes. Only
        # actual movement or resizing invalidates the anchor position.
        if e.widget is self.app.root and self._root_geometry() != self.root_geometry:
            LOG.debug("Workspace popover dismissed after parent geometry changed: before=%s after=%s",
                      self.root_geometry, self._root_geometry())
            self.close(immediate=True)

    def outside(self,e):
        if e.widget is not self.anchor:
            self.close()

    def close(self,immediate=False):
        if self.closed:
            return
        self.closed=True
        if self._show_id is not None:
            self.window.after_cancel(self._show_id)
            self._show_id = None
        self.app.root.unbind("<Button-1>",self.outside_id)
        self.app.root.unbind("<Configure>",self.move_id)
        self.on_close()
        if immediate or not self._shown:
            self.tween.cancel()
            self.window.destroy()
        else:
            start = self.progress
            self.tween.start(lambda p:self.animate(start*(1-p)),self.window.destroy)
        LOG.debug("Workspace popover closed: immediate=%s progress=%.3f",immediate,self.progress)


class ChoiceMenu(AnchoredPanel):
    def __init__(self,app,anchor,title,items,selected,choose,on_close):
        font=ui_font(anchor,11)
        row_height=font.metrics("linespace")+22
        super().__init__(app,anchor,title,width=450,height=105+len(items)*row_height,on_close=on_close)
        self.rows={}
        colors=THEMES[app.preferences["composer_theme"]]
        for key,label in items:
            row=tk.Canvas(self.body,height=row_height,bg=colors.bg,highlightthickness=0,cursor="hand2",takefocus=True)
            row.pack(fill="x")
            def draw(e=None,row=row,key=key,label=label,hover=False):
                row.delete("all")
                w=max(200,row.winfo_width())
                if hover:
                    rounded(row,(2,2,w-2,row_height-2),10,fill=colors.muted,outline="")
                # Leading outlined resource icon, matching the supplied menu.
                row.create_rectangle(12, row_height/2-7,26,row_height/2+7,outline=colors.subtle,width=1.4)
                row.create_line(15,row_height/2-2,23,row_height/2-2,fill=colors.subtle)
                row.create_line(15,row_height/2+2,22,row_height/2+2,fill=colors.subtle)
                row.create_text(40,row_height/2,text=label,font=font,fill=colors.ink,anchor="w")
                if key==selected:
                    row.create_line(w-28,row_height/2,w-24,row_height/2+4,w-17,row_height/2-5,fill=colors.ink,width=2,joinstyle="round")
                row.create_line(8,row_height-1,w-8,row_height-1,fill=colors.border)
            row.bind("<Configure>",draw)
            row.bind("<Enter>",lambda e,draw=draw:draw(hover=True))
            row.bind("<Leave>",lambda e,draw=draw:draw())
            def pick(e=None,key=key):
                self.close()
                choose(key)
                return "break"
            row.bind("<Button-1>",pick)
            row.bind("<Return>",pick)
            row.bind("<space>",pick)
            self.rows[key]=row


class RoundedAnswer(tk.Canvas):
    def __init__(self,parent,theme):
        self.palette=THEMES[theme]
        font=ui_font(parent)
        height=font.metrics("linespace")*2+20
        super().__init__(parent,width=1,height=height,highlightthickness=0,bg=self.palette.bg)
        self.entry=tk.Text(self,height=2,wrap="word",bd=0,highlightthickness=0,relief="flat",undo=True,
                           bg=self.palette.muted,fg=self.palette.ink,insertbackground=self.palette.ink,
                           font=font,padx=0,pady=0)
        self.item=self.create_window(14,10,window=self.entry,anchor="nw")
        self.bind("<Configure>",self.fit)

    def fit(self,e):
        self.itemconfigure(self.item,width=max(1,e.width-28))
        self.delete("surface")
        rounded(self,(1,1,e.width-1,e.height-1),22,fill=self.palette.muted,outline=self.palette.border,tags="surface")
        self.tag_lower("surface")


class SkipButton(GlyphButton):
    def __init__(self,parent,command,theme):
        font=ui_font(parent,11)
        super().__init__(parent,text="跳过",command=command,palette=THEMES[theme],
                         width=font.measure("跳过")+38,height=font.metrics("linespace")+16)

    def _draw(self,e=None):
        self.delete("all")
        w,h=int(self.cget("width")),int(self.cget("height"))
        ink=self.palette.subtle if self.cget("state")=="disabled" else ("#f87171" if self.palette==THEMES["dark"] else "#dc2626")
        if self.hover:
            rounded(self,(1,1,w-1,h-1),12,fill=self.palette.muted,outline="")
        self.create_text(10,h/2,text="跳过",font=ui_font(self,11),fill=ink,anchor="w")
        self.create_line(w-22,h/2-4,w-14,h/2+4,fill=ink,width=1.8,capstyle="round")
        self.create_line(w-22,h/2+4,w-14,h/2-4,fill=ink,width=1.8,capstyle="round")
