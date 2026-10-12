"""Desktop display setup, performed before creating any Tk window."""
import ctypes
import logging
import os

LOG = logging.getLogger(__name__)


def enable_dpi_awareness():
    if os.name != "nt":
        return
    try:
        user32 = ctypes.windll.user32
        # System-aware is stable on the supported Tk 8.6 runtime. Respect an
        # EXE manifest/host that has already chosen a stronger awareness mode.
        setter = user32.SetProcessDpiAwarenessContext
        setter.argtypes = [ctypes.c_void_p]
        setter.restype = ctypes.c_bool
        changed = setter(ctypes.c_void_p(-2))  # DPI_AWARENESS_CONTEXT_SYSTEM_AWARE
        getter = user32.GetThreadDpiAwarenessContext
        getter.restype = ctypes.c_void_p
        awareness = user32.GetAwarenessFromDpiAwarenessContext
        awareness.argtypes = [ctypes.c_void_p]
        LOG.info("Windows DPI awareness: mode=%s newly_set=%s system_dpi=%s",
                 awareness(getter()), changed, user32.GetDpiForSystem())
    except (AttributeError, OSError):
        LOG.warning("Windows DPI setup unavailable; retaining host display mode", exc_info=True)


def display_scale(root):
    return max(1., float(root.tk.call("tk", "scaling"))/(96/72))
