from __future__ import annotations

import argparse
import os
import tkinter as tk

from .ui import PromptSmithApp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PromptSmith 需求引导式提示构建助手")
    parser.add_argument("--smoke-test", action="store_true", help="创建窗口、处理一次刷新后退出")
    parser.add_argument("--verify-release-chain", metavar="DIR", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.verify_release_chain:
        from .release_chain import run_release_chain

        return run_release_chain(args.verify_release_chain)
    root = tk.Tk()
    PromptSmithApp(root)
    if args.smoke_test:
        root.update_idletasks()
        root.update()
        root.destroy()
        return 0
    automatic_close = os.environ.get("PROMPTSMITH_SMOKE_CLOSE_MS")
    if automatic_close:
        root.after(int(automatic_close), root.destroy)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
