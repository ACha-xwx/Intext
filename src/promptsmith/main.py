from __future__ import annotations

import argparse
import logging
import os
import platform
import sys
import time

from .paths import application_data_dir
from .runtime_log import RuntimeLog


def main(argv: list[str] | None = None) -> int:
    startup_started = time.perf_counter()
    parser = argparse.ArgumentParser(description="PromptSmith 需求引导式提示构建助手")
    parser.add_argument("--smoke-test", action="store_true", help="创建窗口、处理一次刷新后退出")
    parser.add_argument("--renderer", choices=("auto", "web", "tk"), default="auto", help="对话渲染引擎（Windows 默认 WebView2）")
    parser.add_argument("--verify-release-chain", metavar="DIR", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.verify_release_chain:
        from .release_chain import run_release_chain

        return run_release_chain(args.verify_release_chain)
    logs = RuntimeLog(application_data_dir() / "logs").start(capture_process=True)
    logs.register_secret(os.environ.get("PROMPTSMITH_API_KEY"))
    logs.register_secret(os.environ.get("PROMPTSMITH_GITHUB_TOKEN"))
    root = None
    app = None
    try:
        logging.getLogger(__name__).info("Runtime environment: Python=%s platform=%s executable=%s cwd=%s frozen=%s renderer=%s",
                                         platform.python_version(), platform.platform(), sys.executable,
                                         os.getcwd(), bool(getattr(sys, "frozen", False)), args.renderer)
        if not args.smoke_test and (args.renderer == "web" or (args.renderer == "auto" and os.name == "nt")):
            try:
                import webview
            except ImportError as exc:
                if args.renderer == "web":
                    raise RuntimeError(
                        "当前 Python 缺少 WebView2 所需依赖。请在项目根目录运行：\n"
                        f'"{sys.executable}" -m pip install -r requirements.txt\n'
                        "安装后重新启动；不要将依赖安装到另一个 Python 环境。"
                    ) from exc
                logging.getLogger(__name__).warning("WebView2 dependency unavailable; using Tk renderer", exc_info=True)
            else:
                from .web_workspace import run_web_workspace, WebRendererUnavailable
                try:
                    return run_web_workspace(logs, automatic_close=os.environ.get("PROMPTSMITH_SMOKE_CLOSE_MS"))
                except WebRendererUnavailable as exc:
                    logging.getLogger(__name__).warning("WebView2 preflight failed: %s", exc, exc_info=True)
                    if args.renderer == "web":
                        from tkinter import messagebox
                        messagebox.showerror("PromptSmith 启动提示", str(exc))
                        return 1
                    logging.getLogger(__name__).info("Continuing startup with Tk renderer after WebView2 preflight failure")
        import tkinter as tk

        from .ui import PromptSmithApp
        from .display import enable_dpi_awareness

        logging.getLogger(__name__).debug("Desktop imports ready: elapsed=%.3fs", time.perf_counter()-startup_started)
        enable_dpi_awareness()
        root = tk.Tk()
        logging.getLogger(__name__).debug("Tk root created: elapsed=%.3fs", time.perf_counter()-startup_started)
        app = PromptSmithApp(root, runtime_log=logs)
        logging.getLogger(__name__).info("Desktop startup initialized: elapsed=%.3fs", time.perf_counter()-startup_started)
        if args.smoke_test:
            root.update_idletasks()
            root.update()
            return 0
        automatic_close = os.environ.get("PROMPTSMITH_SMOKE_CLOSE_MS")
        if automatic_close:
            root.after(int(automatic_close), app.close)
        root.mainloop()
        return 0
    except Exception:
        logging.getLogger(__name__).exception("Desktop startup or main loop failed")
        raise
    finally:
        try:
            if app is not None:
                try:
                    app.shutdown(wait=True)
                finally:
                    app.executor.shutdown(wait=True, cancel_futures=True)
        except Exception:
            logging.getLogger(__name__).exception("Desktop shutdown failed")
            raise
        finally:
            try:
                if root is not None:
                    try:
                        root.destroy()
                    except tk.TclError:
                        logging.getLogger(__name__).debug("Tk root already destroyed", exc_info=True)
            finally:
                logs.close()


if __name__ == "__main__":
    raise SystemExit(main())
