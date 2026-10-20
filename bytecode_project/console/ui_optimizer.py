"""Non-invasive UI/UX enhancement layer for the recovered Tk application."""

from __future__ import annotations

import json
import os
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any


PALETTE = {
    "bg": "#0b1220",
    "panel": "#111c2e",
    "panel_alt": "#17253a",
    "line": "#263a56",
    "text": "#eaf2ff",
    "muted": "#9fb2cc",
    "accent": "#3b82f6",
    "accent_hover": "#60a5fa",
    "success": "#22c55e",
    "danger": "#ef4444",
}


def _walk(widget: tk.Misc):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _text(widget: tk.Misc) -> str:
    try:
        return str(widget.cget("text"))
    except Exception:
        return ""


def _invoke_button(root: tk.Misc, label: str) -> bool:
    for widget in _walk(root):
        if isinstance(widget, (tk.Button, ttk.Button)) and _text(widget) == label:
            widget.invoke()
            return True
    return False


def _copy_tree(tree: ttk.Treeview, root: tk.Misc) -> None:
    selected = tree.selection()
    if not selected:
        return
    lines = []
    for ident in selected:
        values = tree.item(ident, "values")
        lines.append("\t".join(str(value) for value in values))
    root.clipboard_clear()
    root.clipboard_append("\n".join(lines))


def install_ui_optimizations(App: type) -> None:
    """Patch shared widget factories before the application is constructed."""
    if getattr(App, "_ui_optimizer_installed", False):
        return
    App._ui_optimizer_installed = True

    original_style = App.style
    original_button = App.button
    original_table = App.table
    original_fill = App.fill
    original_show = App.show
    original_preserve_captcha_key = App.preserve_captcha_key

    def style(self):
        result = original_style(self)
        theme = ttk.Style(self.root)
        try:
            theme.theme_use("clam")
        except tk.TclError:
            pass
        theme.configure("TFrame", background=PALETTE["bg"])
        theme.configure("TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=("Microsoft YaHei UI", 10))
        theme.configure("TButton", background=PALETTE["panel_alt"], foreground=PALETTE["text"], padding=(14, 8), font=("Microsoft YaHei UI", 10), borderwidth=0)
        theme.map("TButton", background=[("active", PALETTE["line"]), ("pressed", PALETTE["accent"])], foreground=[("disabled", PALETTE["muted"])])
        theme.configure("Accent.TButton", background=PALETTE["accent"], foreground="#ffffff", font=("Microsoft YaHei UI", 10, "bold"))
        theme.map("Accent.TButton", background=[("active", PALETTE["accent_hover"]), ("pressed", "#2563eb")])
        theme.configure("Nav.Active.TButton", background=PALETTE["accent"], foreground="#ffffff", font=("Microsoft YaHei UI", 10, "bold"))
        theme.configure("Treeview", background=PALETTE["panel"], fieldbackground=PALETTE["panel"], foreground=PALETTE["text"], rowheight=31, font=("Microsoft YaHei UI", 9))
        theme.configure("Treeview.Heading", background=PALETTE["panel_alt"], foreground=PALETTE["text"], relief="flat", padding=(7, 8), font=("Microsoft YaHei UI", 9, "bold"))
        theme.map("Treeview", background=[("selected", PALETTE["accent"])], foreground=[("selected", "#ffffff")])
        theme.configure("TEntry", fieldbackground="#f8fafc", foreground="#0f172a", padding=6)
        theme.configure("TCombobox", fieldbackground="#f8fafc", foreground="#0f172a", padding=5)
        theme.configure("TNotebook.Tab", padding=(14, 8), font=("Microsoft YaHei UI", 9))
        return result

    def button(self, parent, text, command, accent=False):
        widget = original_button(self, parent, text, command, accent)
        if widget is not None:
            try:
                widget.configure(cursor="hand2", takefocus=True)
            except tk.TclError:
                pass
        return widget

    def table(self, parent, cols, widths=None, height=12):
        tree = original_table(self, parent, cols, widths, height)
        try:
            tree.tag_configure("even", background=PALETTE["panel"])
            tree.tag_configure("odd", background=PALETTE["panel_alt"])
            tree.bind("<Control-c>", lambda _e, t=tree: _copy_tree(t, self.root), add="+")
            tree.bind("<Control-C>", lambda _e, t=tree: _copy_tree(t, self.root), add="+")
            menu = tk.Menu(tree, tearoff=False)
            menu.add_command(label="复制选中行", command=lambda t=tree: _copy_tree(t, self.root))
            menu.add_command(label="全选", command=lambda t=tree: t.selection_set(t.get_children()))
            tree.bind("<Button-3>", lambda e, m=menu: m.tk_popup(e.x_root, e.y_root), add="+")
        except Exception:
            pass
        return tree

    def fill(self, tree, rows, keys, id_key="id"):
        result = original_fill(self, tree, rows, keys, id_key)
        try:
            for index, ident in enumerate(tree.get_children()):
                tree.item(ident, tags=(("even" if index % 2 == 0 else "odd"),))
        except Exception:
            pass
        return result

    def show(self, name):
        result = original_show(self, name)
        self._ui_current_page = name
        for widget in _walk(self.root):
            if isinstance(widget, ttk.Button) and _text(widget) in self.pages:
                widget.configure(style="Nav.Active.TButton" if _text(widget) == name else "TButton")
        return result

    def preserve_captcha_key(self):
        result = original_preserve_captcha_key(self)
        _sync_captcha_runtime(self, persist=True)
        return result

    App.style = style
    App.button = button
    App.table = table
    App.fill = fill
    App.show = show
    App.preserve_captcha_key = preserve_captcha_key


def _sync_captcha_runtime(app: Any, *, persist: bool = False) -> bool:
    """Keep the saved 2Captcha key and the engine enable flag in sync.

    The recovered UI contained a toggle handler but never created its Tk
    variable/control, leaving ``engine.captcha_enabled`` permanently false.
    A locally encrypted, non-empty key now enables the runtime automatically.
    """
    variable = getattr(app, "captcha_key", None)
    key = str(variable.get() if variable is not None else getattr(app.engine, "captcha_key", "") or "").strip()
    app.engine.captcha_key = key
    app.engine.captcha_enabled = bool(key)
    if persist:
        app.store.set_setting("captcha_enabled", "是" if key else "否")
    try:
        app.store.log(
            "INFO",
            "",
            "captcha",
            "2Captcha 自动验证已启用" if key else "2Captcha 自动验证未启用：未检测到已保存密钥",
        )
    except Exception:
        pass
    return bool(key)


class UIEnhancer:
    def __init__(self, app: Any, root: tk.Tk, home: Path, health: dict[str, Any]):
        self.app = app
        self.root = root
        self.home = Path(home)
        self.health = health
        self.state_path = self.home / "ui-state.json"
        self.scale = 1.0

    def apply(self) -> None:
        _sync_captcha_runtime(self.app, persist=True)
        self._load_state()
        self._menu()
        self._shortcuts()
        self._polish_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _load_state(self) -> None:
        try:
            state = json.loads(self.state_path.read_text("utf-8"))
        except Exception:
            state = {}
        geometry = str(state.get("geometry", ""))
        if "x" in geometry and "+" in geometry:
            try:
                self.root.geometry(geometry)
            except tk.TclError:
                pass
        self.scale = float(state.get("scale", 1.0))
        self._set_scale(self.scale, save=False)
        page = state.get("page")
        if page in self.app.pages:
            self.app.show(page)

    def _save_state(self) -> None:
        state = {
            "geometry": self.root.geometry(),
            "page": getattr(self.app, "_ui_current_page", "运行总览"),
            "scale": self.scale,
        }
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def close(self) -> None:
        try:
            self._save_state()
        finally:
            self.app.close()

    def _menu(self) -> None:
        menu = tk.Menu(self.root, tearoff=False, font=("Microsoft YaHei UI", 9))
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="打开数据目录", command=lambda: os.startfile(self.home))
        file_menu.add_command(label="打开备份目录", command=self._open_backups)
        file_menu.add_separator()
        file_menu.add_command(label="退出", accelerator="Alt+F4", command=self.close)
        menu.add_cascade(label="文件", menu=file_menu)

        run_menu = tk.Menu(menu, tearoff=False)
        run_menu.add_command(label="开始 / 继续", accelerator="F9", command=lambda: _invoke_button(self.root, "开始 / 继续"))
        run_menu.add_command(label="暂停", accelerator="F10", command=lambda: _invoke_button(self.root, "暂停"))
        run_menu.add_command(label="停止全部", accelerator="Shift+F10", command=lambda: _invoke_button(self.root, "停止全部"))
        run_menu.add_separator()
        run_menu.add_command(label="刷新界面", accelerator="F5", command=self.app.refresh_views)
        menu.add_cascade(label="运行", menu=run_menu)

        view_menu = tk.Menu(menu, tearoff=False)
        for index, page in enumerate(self.app.pages, 1):
            accelerator = f"Ctrl+{index}" if index <= 9 else ""
            view_menu.add_command(label=page, accelerator=accelerator, command=lambda p=page: self.app.show(p))
        view_menu.add_separator()
        view_menu.add_command(label="页面快速切换", accelerator="Ctrl+K", command=self.command_palette)
        view_menu.add_command(label="放大界面", accelerator="Ctrl++", command=lambda: self._set_scale(self.scale + 0.1))
        view_menu.add_command(label="缩小界面", accelerator="Ctrl+-", command=lambda: self._set_scale(self.scale - 0.1))
        view_menu.add_command(label="恢复默认比例", accelerator="Ctrl+0", command=lambda: self._set_scale(1.0))
        menu.add_cascade(label="视图", menu=view_menu)

        tools = tk.Menu(menu, tearoff=False)
        tools.add_command(label="系统健康中心", accelerator="Ctrl+H", command=self.health_dialog)
        tools.add_command(label="立即备份数据库", command=self.manual_backup)
        tools.add_command(label="获取模拟器窗口", command=lambda: _invoke_button(self.root, "获取模拟器窗口"))
        tools.add_command(label="系统设置", command=lambda: self.app.show("系统设置"))
        menu.add_cascade(label="工具", menu=tools)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="快捷键说明", accelerator="F1", command=self.shortcuts_dialog)
        help_menu.add_command(label="关于优化版", command=self.about_dialog)
        menu.add_cascade(label="帮助", menu=help_menu)
        self.root.configure(menu=menu)

    def _shortcuts(self) -> None:
        self.root.bind_all("<F1>", lambda _e: self.shortcuts_dialog())
        self.root.bind_all("<F5>", lambda _e: self.app.refresh_views())
        self.root.bind_all("<F9>", lambda _e: _invoke_button(self.root, "开始 / 继续"))
        self.root.bind_all("<F10>", lambda _e: _invoke_button(self.root, "暂停"))
        self.root.bind_all("<Shift-F10>", lambda _e: _invoke_button(self.root, "停止全部"))
        self.root.bind_all("<Control-k>", lambda _e: self.command_palette())
        self.root.bind_all("<Control-h>", lambda _e: self.health_dialog())
        self.root.bind_all("<Control-plus>", lambda _e: self._set_scale(self.scale + 0.1))
        self.root.bind_all("<Control-minus>", lambda _e: self._set_scale(self.scale - 0.1))
        self.root.bind_all("<Control-0>", lambda _e: self._set_scale(1.0))
        for index, page in enumerate(self.app.pages, 1):
            if index <= 9:
                self.root.bind_all(f"<Control-Key-{index}>", lambda _e, p=page: self.app.show(p))

    def _polish_widgets(self) -> None:
        for widget in _walk(self.root):
            if isinstance(widget, (ttk.Button, tk.Button)):
                try:
                    widget.configure(cursor="hand2", takefocus=True)
                except tk.TclError:
                    pass
            elif isinstance(widget, ttk.Treeview):
                widget.configure(selectmode="extended")
            elif isinstance(widget, tk.Text):
                widget.configure(insertbackground=PALETTE["text"], undo=True, maxundo=100)
            elif isinstance(widget, ttk.Label):
                text = _text(widget)
                if text.startswith("连接测试会显示余额。Signal 验证页"):
                    enabled = bool(getattr(self.app.engine, "captcha_enabled", False))
                    widget.configure(
                        text=(
                            "状态：自动验证已启用。检测到 Signal hCaptcha 后会提交到 2Captcha，完成后自动继续注册。"
                            if enabled else
                            "状态：自动验证未启用。请填写并本机加密保存 2Captcha API 密钥。"
                        )
                    )

    def _set_scale(self, value: float, save: bool = True) -> None:
        self.scale = min(1.4, max(0.85, round(value, 2)))
        base = 10
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                font = tkfont.nametofont(name)
                font.configure(family="Microsoft YaHei UI", size=max(8, round(base * self.scale)))
            except tk.TclError:
                pass
        try:
            ttk.Style(self.root).configure("Treeview", rowheight=max(26, round(31 * self.scale)))
        except tk.TclError:
            pass
        if save:
            self._save_state()

    def command_palette(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("快速切换页面")
        dialog.geometry("440x430")
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text="输入页面名称", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        query = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=query)
        entry.pack(fill="x", padx=18, pady=(0, 10))
        listing = tk.Listbox(dialog, bg=PALETTE["panel"], fg=PALETTE["text"], selectbackground=PALETTE["accent"], relief="flat", font=("Microsoft YaHei UI", 11), activestyle="none")
        listing.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        def refresh(*_):
            needle = query.get().strip().lower()
            listing.delete(0, "end")
            for page in self.app.pages:
                if needle in page.lower():
                    listing.insert("end", page)
            if listing.size():
                listing.selection_set(0)

        def choose(_event=None):
            if listing.curselection():
                self.app.show(listing.get(listing.curselection()[0]))
                dialog.destroy()

        query.trace_add("write", refresh)
        listing.bind("<Double-1>", choose)
        listing.bind("<Return>", choose)
        entry.bind("<Return>", choose)
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        refresh()
        entry.focus_set()

    def health_dialog(self) -> None:
        checks = self.health.get("checks", {})
        rows = [f"健康评分：{self.health.get('score', '-')} / 100", f"数据库：{self.health.get('database', {}).get('quick_check', '-')}"]
        labels = {
            "data_directory_writable": "数据目录可写",
            "disk_free_over_5gb": "磁盘空间",
            "adb_exists": "ADB 工具",
            "manager_exists": "MuMu 管理器",
        }
        rows.extend(f"{'✓' if checks.get(key) else '✗'}  {label}" for key, label in labels.items())
        rows.append(f"\n最近备份：{self.health.get('backup', '-')}\n健康报告：{self.home / 'health-latest.json'}")
        messagebox.showinfo("系统健康中心", "\n".join(rows), parent=self.root)

    def manual_backup(self) -> None:
        from console.optimizer import backup_database
        path = backup_database(self.app.store, self.home, min_age_hours=0)
        messagebox.showinfo("备份完成", f"数据库已备份到：\n{path}", parent=self.root)

    def _open_backups(self) -> None:
        path = self.home / "backups"
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)

    def shortcuts_dialog(self) -> None:
        messagebox.showinfo(
            "快捷键",
            "Ctrl+K  快速切换页面\nCtrl+1～9  打开常用页面\nF5  刷新界面\nF9  开始 / 继续\nF10  暂停\nShift+F10  停止全部\nCtrl+H  系统健康中心\nCtrl++ / Ctrl+-  缩放界面\nCtrl+C  复制表格选中行",
            parent=self.root,
        )

    def about_dialog(self) -> None:
        messagebox.showinfo("关于", "多窗口模拟器自动化控制台\n2026.10 全面优化界面版\n\n13 个功能页面 · 健康检查 · 自动备份 · 快捷导航", parent=self.root)


def enhance_app(app: Any, root: tk.Tk, home: Path, health: dict[str, Any]) -> UIEnhancer:
    enhancer = UIEnhancer(app, root, home, health)
    enhancer.apply()
    return enhancer


__all__ = ["install_ui_optimizations", "enhance_app", "UIEnhancer", "PALETTE", "_sync_captcha_runtime"]
