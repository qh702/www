"""Repair layer for the recovered registration controller.

It delegates all original behaviour to ``registration.pyc`` and only fills in
the missing CAPTCHA branch.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

from console.signal_contract import BACKUP_PAGE_MARKERS, BACKUP_SKIP_LABELS


def _load_original():
    path = Path(__file__).with_suffix(".pyc")
    name = "console.signal_support._registration_original"
    loader = importlib.machinery.SourcelessFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    if spec is None:
        raise ImportError(f"cannot create loader spec for {path}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


_original = _load_original()

for _name, _value in vars(_original).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

_original_tick = Session.tick
_original_screen_kind = Screen.kind

def _screen_strings(screen):
    values = set()
    for node in getattr(screen, "nodes", ()):
        for key in ("text", "content-desc"):
            value = str(node.get(key, "") or "").strip()
            if value:
                values.add(value)
    values.update(str(value).strip() for value in getattr(screen, "texts", ()) if str(value).strip())
    return values


def _is_backup_restore_choice(screen):
    values = _screen_strings(screen)
    return bool(values.intersection(BACKUP_PAGE_MARKERS)) and bool(values.intersection(BACKUP_SKIP_LABELS))


def _backup_skip_node(screen):
    found = []
    for node in getattr(screen, "nodes", ()):
        text = str(node.get("text", "") or "").strip()
        desc = str(node.get("content-desc", "") or "").strip()
        if text in BACKUP_SKIP_LABELS or desc in BACKUP_SKIP_LABELS:
            found.append(node)
    if len(found) != 1:
        raise PauseRequired(f"备份选择页的‘不转移并继续’按钮数量异常：{len(found)}")
    return found[0]


def _screen_kind(self):
    kind = _original_screen_kind(self)
    if kind in {"unknown", "other"} and _is_backup_restore_choice(self):
        return "backup_restore_choice"
    return kind


Screen.kind = _screen_kind


def _captcha_tick(self, screen):
    kind = screen.kind()
    if kind == "backup_restore_choice":
        self.driver.tap(_backup_skip_node(screen))
        self.data["backup_restore_skipped"] = True
        self.record("backup_restore_skipped", "已选择不转移并继续，进入后续注册步骤。")
        return "progress"

    if kind != "verification_webview":
        return _original_tick(self, screen)

    if self.captcha_solver is None:
        raise PauseRequired("检测到验证码页面，请在模拟器中手动完成验证。")

    # Signal 8.30.3 keeps the CAPTCHA callback inside a private WebViewClient.
    # Once this has been detected, keep the registration task alive and poll
    # for the next screen instead of repeatedly invoking the solver or moving
    # the task into a paused/manual state.
    if self.data.get("manual_captcha_pending"):
        return "wait_transition"

    if self.data.get("webview_captcha_processed"):
        return "wait_transition"

    from console.captcha_solver import SignalCaptchaHandler

    screenshot_path = None
    try:
        screenshot_path = self.driver.device.screenshot()
    except Exception:
        pass

    handler = SignalCaptchaHandler(self.driver.device, self.captcha_solver)
    result = handler.solve_and_submit(screenshot_path)
    attempts = int(self.data.get("captcha_attempts", 0)) + 1
    self.data["captcha_attempts"] = attempts

    if result.get("success"):
        self.data["webview_captcha_processed"] = True
        self.record("captcha_submitted", result.get("message", "验证码 token 已提交"))
        return "wait_transition"

    message = str(result.get("message") or "2Captcha 自动验证失败")
    if "未导出 CAPTCHA 回调 Activity" in message:
        self.data["manual_captcha_pending"] = True
        self.record(
            "captcha_waiting",
            "验证页保持打开；任务继续监测，页面验证完成后将自动进入下一步。",
        )
        return "wait_transition"

    self.record("captcha_failed", message)
    raise PauseRequired(message)


Session.tick = _captcha_tick

__all__ = [name for name in vars(_original) if not name.startswith("_")]
