"""One packaged brand resource for the native and web desktops."""
import logging
import tkinter as tk
from .paths import resource_root

LOG = logging.getLogger(__name__)


def brand_path(name="intext.ico"):
    return resource_root() / "resources/ui/workspace/brand" / name


def apply_window_icon(window):
    try:
        image = tk.PhotoImage(master=window, file=str(brand_path("intext-logo-32.png")))
        window.iconphoto(True, image)
        window._intext_icon = image
        if window.tk.call("tk", "windowingsystem") == "win32":
            window.iconbitmap(default=str(brand_path()))
        LOG.debug("Intext native window icon applied")
    except (OSError, tk.TclError):
        LOG.warning("Intext native window icon unavailable; system icon retained", exc_info=True)
