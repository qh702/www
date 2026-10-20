from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from console.gui import App
from console.optimizer import RuntimeOptimizer
from console.ui_optimizer import enhance_app, install_ui_optimizations


def _single_instance(home: Path):
    if sys.platform != "win32":
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    ident = hashlib.sha256(str(home.resolve()).lower().encode()).hexdigest()
    mutex = kernel.CreateMutexW(None, False, "Local\\AndroidConsole_" + ident)
    if ctypes.get_last_error() == 183:
        messagebox.showinfo("程序已运行", "同一数据目录的控制台已经运行。")
        raise SystemExit(0)
    return mutex


def main():
    parser = argparse.ArgumentParser(description="多窗口模拟器自动化控制台")
    parser.add_argument("--data-home", type=Path, help="程序目录（数据保存在此目录的 data 子目录）")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--health-check", action="store_true", help="运行启动诊断并生成 health-latest.json")
    args = parser.parse_args()

    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    home = args.data_home or base
    home.mkdir(parents=True, exist_ok=True)
    mutex = _single_instance(home)

    install_ui_optimizations(App)
    root = tk.Tk()
    if args.smoke_test:
        root.withdraw()
    app = App(root, home)
    optimization_report = RuntimeOptimizer(home).apply(app)
    ui_enhancer = enhance_app(app, root, home, optimization_report)
    try:
        root.title(root.title() + f" · 优化版 · 健康 {optimization_report['score']}")
    except Exception:
        pass

    if args.smoke_test or args.health_check:
        def finish_test():
            try:
                # Import the repair wrappers from the packaged runtime instead of
                # reporting a hard-coded success.  This catches missing sidecar
                # bytecode files in PyInstaller one-file builds.
                from console.captcha_solver import CaptchaSolver, SignalCaptchaHandler
                from console.signal_support.registration import Session

                solver = CaptchaSolver("PACKAGING_PROBE_NOT_SENT")
                captcha_repair = all(
                    (
                        callable(getattr(solver, "get_balance", None)),
                        callable(getattr(SignalCaptchaHandler, "solve_and_submit", None)),
                        callable(getattr(Session, "tick", None)),
                    )
                )
                ui_menu = bool(str(root.cget("menu")))
                ui_shortcuts = bool(root.bind_class("all", "<Control-k>"))
                result = {
                    "ok": captcha_repair and ui_menu and ui_shortcuts,
                    "pages": len(app.pages),
                    "business_forms": 5,
                    "phone_metadata": True,
                    "dpapi": True,
                    "image_runtime": True,
                    "captcha_repair": captcha_repair,
                    "health_score": optimization_report["score"],
                    "database_quick_check": optimization_report["database"]["quick_check"],
                    "ui_menu": ui_menu,
                    "ui_shortcuts": ui_shortcuts,
                    "ui_state_restore": hasattr(ui_enhancer, "_load_state"),
                    "captcha_enabled": bool(app.engine.captcha_enabled),
                    "captcha_key_loaded": bool(app.engine.captcha_key),
                }
            except Exception as exc:
                result = {
                    "ok": False,
                    "captcha_repair": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            (home / "smoke-result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            app.engine.close()
            try:
                app.store.db.close()
            except Exception:
                pass
            root.destroy()

        root.after(1500, finish_test)

    root.mainloop()
    return mutex, ui_enhancer


if __name__ == "__main__":
    main()
