"""Runtime repair layer for the recovered 2Captcha module.

The original Python 3.12 bytecode is kept as ``captcha_solver.pyc``.  This
source module loads it, preserves its API client, and replaces only the
unfinished Signal result-submission method.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import time
from pathlib import Path
from typing import Any


def _load_original():
    path = Path(__file__).with_suffix(".pyc")
    name = "console._captcha_solver_original"
    loader = importlib.machinery.SourcelessFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    if spec is None:
        raise ImportError(f"cannot create loader spec for {path}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


_original = _load_original()
CaptchaSolver = _original.CaptchaSolver
SignalCaptchaHandler = _original.SignalCaptchaHandler
test_solver = _original.test_solver

SIGNAL_PACKAGE = "org.thoughtcrime.securesms"
SIGNAL_CAPTCHA_SCHEME = "signalcaptcha://"


def _clean_token(value: Any) -> str:
    token = str(value or "").strip()
    if token.startswith(SIGNAL_CAPTCHA_SCHEME):
        token = token[len(SIGNAL_CAPTCHA_SCHEME) :]
    if not token or len(token) < 20:
        raise ValueError("2Captcha 返回了空或过短的 hCaptcha token")
    if re.search(r"[\s\x00-\x1f]", token):
        raise ValueError("2Captcha token 包含非法空白或控制字符")
    return token


def _submit_deep_link(device: Any, token: str) -> str:
    uri = SIGNAL_CAPTCHA_SCHEME + token
    result = device.command(
        [
            "shell",
            "am",
            "start",
            "-W",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            uri,
            "-p",
            SIGNAL_PACKAGE,
        ],
        timeout=30,
    )
    text = str(result or "")
    lowered = text.lower()
    failure_markers = (
        "error:",
        "exception",
        "no activity found",
        "unable to resolve intent",
        "activity not started",
    )
    if any(marker in lowered for marker in failure_markers):
        raise RuntimeError("Signal CAPTCHA deep link 提交失败: " + text[-500:])
    return text


def _callback_activity_available(device: Any) -> bool:
    """Return whether this APK exposes an Activity for the callback scheme."""
    result = device.command(
        [
            "shell",
            "cmd",
            "package",
            "resolve-activity",
            "--brief",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            SIGNAL_CAPTCHA_SCHEME + "CONTRACT_PROBE",
            SIGNAL_PACKAGE,
        ],
        timeout=15,
    )
    text = str(result or "").strip().lower()
    if not text or "no activity found" in text or "unable to resolve" in text:
        return False
    return SIGNAL_PACKAGE in text


def _solve_and_submit(self, screenshot_path=None):
    """Solve the visible Signal hCaptcha and return its token to Signal.

    Signal 8.30.3 returns ``signalcaptcha://<token>`` from inside its WebView.
    The APK does not export an Activity for that scheme, so an external ADB
    VIEW intent is accepted only when a future build explicitly declares one.
    """

    try:
        # The recovered method owns screenshot capture and takes no arguments.
        # Passing screenshot_path caused the live TypeError seen in task #3.
        info = self.extract_hcaptcha_info()
        if not isinstance(info, dict):
            return {"success": False, "message": "未提取到 hCaptcha 页面信息"}

        sitekey = str(info.get("sitekey") or "").strip()
        page_url = str(info.get("url") or info.get("page_url") or "").strip()
        if not sitekey or not page_url:
            return {
                "success": False,
                "message": "未提取到 hCaptcha sitekey 或页面 URL",
            }

        # Avoid charging a solve when the installed APK cannot receive an
        # external callback.  Signal 8.30.3 handles this scheme only inside
        # its private WebViewClient.
        if not _callback_activity_available(self.device):
            return {
                "success": False,
                "message": (
                    "当前 Signal 8.30.3 未导出 CAPTCHA 回调 Activity；"
                    "已停止外部提交并保留页面，请在模拟器中完成验证后继续。"
                ),
            }

        solved = self.solver.solve_hcaptcha(sitekey, page_url, screenshot_path)
        if not isinstance(solved, dict) or not solved.get("success"):
            error = solved.get("error") if isinstance(solved, dict) else solved
            return {"success": False, "message": f"2Captcha 识别失败: {error}"}

        token = _clean_token(solved.get("token"))
        _submit_deep_link(self.device, token)
        time.sleep(2)
        return {
            "success": True,
            "message": "2Captcha token 已提交给 Signal，正在等待页面切换",
        }
    except Exception as exc:
        return {"success": False, "message": f"自动验证失败: {exc}"}


SignalCaptchaHandler.solve_and_submit = _solve_and_submit

__all__ = ["CaptchaSolver", "SignalCaptchaHandler", "test_solver"]
