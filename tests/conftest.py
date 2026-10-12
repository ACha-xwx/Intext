from __future__ import annotations

import tkinter as tk

import pytest


@pytest.fixture(autouse=True)
def isolated_application_data(tmp_path, monkeypatch):
    """UI confirmation must never overwrite a developer's saved settings."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    for name in ("PROMPTSMITH_API_KEY", "PROMPTSMITH_GITHUB_TOKEN", "PROMPTSMITH_PROVIDER",
                 "PROMPTSMITH_API_BASE_URL", "PROMPTSMITH_MODEL", "PROMPTSMITH_SKILL_SEARCH_URL",
                 "PROMPTSMITH_WEB_SEARCH_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def fail_unexpected_error_dialog(monkeypatch):
    """An unmocked error must fail automation rather than wait for a human."""
    def unexpected(title, message, **_kwargs):
        pytest.fail(f"Unexpected UI error dialog [{title}]: {message}")
    monkeypatch.setattr("tkinter.messagebox.showerror", unexpected)
    monkeypatch.setattr("tkinter.messagebox.showwarning", unexpected)


@pytest.fixture(scope="session")
def tk_root():
    """Keep one Tcl/Tk interpreter for the full Windows test process."""
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()
