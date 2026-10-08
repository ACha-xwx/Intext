from __future__ import annotations

import tkinter as tk

import pytest


@pytest.fixture(autouse=True)
def fail_unexpected_error_dialog(monkeypatch):
    """An unmocked error must fail automation rather than wait for a human."""
    def unexpected(title, message, **_kwargs):
        pytest.fail(f"Unexpected UI error dialog [{title}]: {message}")
    monkeypatch.setattr("tkinter.messagebox.showerror", unexpected)


@pytest.fixture(scope="session")
def tk_root():
    """Keep one Tcl/Tk interpreter for the full Windows test process."""
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()
