from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "bytecode_project"
sys.path.insert(0, str(ROOT))

from console.captcha_solver import CaptchaSolver, SignalCaptchaHandler
from console.signal_support.registration import Screen, Session


class FakeDevice:
    def __init__(self):
        self.calls = []

    def command(self, args, timeout=0, binary=False):
        self.calls.append((args, timeout, binary))
        if "resolve-activity" in args:
            return "org.thoughtcrime.securesms/.CaptchaCallbackActivity"
        return "Status: ok\nActivity: org.thoughtcrime.securesms/.RoutingActivity"

    def screenshot(self):
        return "fixture.png"


class FakeScreen:
    def kind(self):
        return "verification_webview"


class BackupScreen:
    def __init__(self):
        self.nodes = [
            {"text": "還原或轉移帳戶", "enabled": "true", "bounds": "[0,0][100,50]"},
            {"text": "選擇要還原訊息紀錄和帳戶資料的方式。", "enabled": "true", "bounds": "[0,50][100,100]"},
            {"text": "不轉移並繼續", "enabled": "true", "bounds": "[0,100][200,160]"},
        ]
        self.texts = {node["text"] for node in self.nodes}

    def kind(self):
        # Exercise the repaired Session branch without a live XML hierarchy.
        return "backup_restore_choice"


class FakeDriver:
    def __init__(self, device):
        self.device = device
        self.tapped = []

    def tap(self, node):
        self.tapped.append(node)


class CaptchaRepairTests(unittest.TestCase):
    def test_token_is_returned_to_signal(self):
        device = FakeDevice()
        solver = CaptchaSolver("TEST_KEY_NOT_SENT")
        solver.solve_hcaptcha = lambda *args, **kwargs: {
            "success": True,
            "token": "P1_TEST_TOKEN_abcdefghijklmnopqrstuvwxyz0123456789",
        }
        handler = SignalCaptchaHandler(device, solver)
        extract_calls = []
        handler.extract_hcaptcha_info = lambda: extract_calls.append(True) or {
            "sitekey": "10000000-ffff-ffff-ffff-000000000001",
            "url": "https://signalcaptchas.org/registration/generate.html",
        }

        result = handler.solve_and_submit("fixture.png")

        self.assertTrue(result["success"])
        self.assertEqual(extract_calls, [True])
        self.assertEqual(len(device.calls), 2)
        args = device.calls[1][0]
        self.assertEqual(args[:4], ["shell", "am", "start", "-W"])
        self.assertTrue(any(
            value.startswith("signalcaptcha://P1_TEST_TOKEN_")
            for value in args
        ))
        self.assertIn("org.thoughtcrime.securesms", args)

    def test_solver_failure_does_not_launch_signal(self):
        device = FakeDevice()
        solver = CaptchaSolver("TEST_KEY_NOT_SENT")
        solver.solve_hcaptcha = lambda *args, **kwargs: {
            "success": False,
            "error": "fixture failure",
        }
        handler = SignalCaptchaHandler(device, solver)
        handler.extract_hcaptcha_info = lambda: {
            "sitekey": "10000000-ffff-ffff-ffff-000000000001",
            "url": "https://signalcaptchas.org/registration/generate.html",
        }

        result = handler.solve_and_submit()

        self.assertFalse(result["success"])
        self.assertEqual(len(device.calls), 1)
        self.assertIn("resolve-activity", device.calls[0][0])

    def test_registration_branch_submits_only_once(self):
        device = FakeDevice()
        solver = CaptchaSolver("TEST_KEY_NOT_SENT")
        solver.solve_hcaptcha = lambda *args, **kwargs: {
            "success": True,
            "token": "P1_TEST_TOKEN_abcdefghijklmnopqrstuvwxyz0123456789",
        }

        # Avoid depending on a real emulator hierarchy in this fixture.
        old_extract = SignalCaptchaHandler.extract_hcaptcha_info
        SignalCaptchaHandler.extract_hcaptcha_info = lambda self: {
            "sitekey": "10000000-ffff-ffff-ffff-000000000001",
            "url": "https://signalcaptchas.org/registration/generate.html",
        }
        try:
            session = Session.__new__(Session)
            session.driver = FakeDriver(device)
            session.captcha_solver = solver
            session.data = {}
            records = []
            session.record = lambda state, message: records.append((state, message))

            first = session.tick(FakeScreen())
            second = session.tick(FakeScreen())

            self.assertEqual(first, "wait_transition")
            self.assertEqual(second, "wait_transition")
            self.assertTrue(session.data["webview_captcha_processed"])
            self.assertEqual(session.data["captcha_attempts"], 1)
            self.assertEqual(len(device.calls), 2)
            self.assertEqual(records[0][0], "captcha_submitted")
        finally:
            SignalCaptchaHandler.extract_hcaptcha_info = old_extract

    def test_unresolved_deep_link_is_not_reported_as_success(self):
        class UnresolvedDevice(FakeDevice):
            def command(self, args, timeout=0, binary=False):
                self.calls.append((args, timeout, binary))
                if "resolve-activity" in args:
                    return "No activity found"
                return "Error: Activity not started, unable to resolve Intent; No Activity found"

        device = UnresolvedDevice()
        solver = CaptchaSolver("TEST_KEY_NOT_SENT")
        solver.solve_hcaptcha = lambda *args, **kwargs: {
            "success": True,
            "token": "P1_TEST_TOKEN_abcdefghijklmnopqrstuvwxyz0123456789",
        }
        handler = SignalCaptchaHandler(device, solver)
        handler.extract_hcaptcha_info = lambda: {
            "sitekey": "10000000-ffff-ffff-ffff-000000000001",
            "url": "https://signalcaptchas.org/registration/generate.html",
        }

        result = handler.solve_and_submit()

        self.assertFalse(result["success"])
        self.assertIn("未导出", result["message"])
        self.assertEqual(len(device.calls), 1)

    def test_unexported_callback_keeps_task_running_and_waits_for_next_page(self):
        class UnresolvedDevice(FakeDevice):
            def command(self, args, timeout=0, binary=False):
                self.calls.append((args, timeout, binary))
                if "resolve-activity" in args:
                    return "No activity found"
                return "Status: ok"

        device = UnresolvedDevice()
        solver = CaptchaSolver("TEST_KEY_NOT_SENT")
        solve_calls = []
        solver.solve_hcaptcha = lambda *args, **kwargs: solve_calls.append(True) or {
            "success": True,
            "token": "P1_TEST_TOKEN_abcdefghijklmnopqrstuvwxyz0123456789",
        }

        old_extract = SignalCaptchaHandler.extract_hcaptcha_info
        SignalCaptchaHandler.extract_hcaptcha_info = lambda self: {
            "sitekey": "10000000-ffff-ffff-ffff-000000000001",
            "url": "https://signalcaptchas.org/registration/generate.html",
        }
        try:
            session = Session.__new__(Session)
            session.driver = FakeDriver(device)
            session.captcha_solver = solver
            session.data = {}
            records = []
            session.record = lambda state, message: records.append((state, message))

            first = session.tick(FakeScreen())
            second = session.tick(FakeScreen())

            self.assertEqual(first, "wait_transition")
            self.assertEqual(second, "wait_transition")
            self.assertTrue(session.data["manual_captcha_pending"])
            self.assertEqual(session.data["captcha_attempts"], 1)
            self.assertEqual(solve_calls, [])
            self.assertEqual([state for state, _ in records], ["captcha_waiting"])
            self.assertEqual(len(device.calls), 1)
        finally:
            SignalCaptchaHandler.extract_hcaptcha_info = old_extract

    def test_backup_restore_choice_skips_transfer_and_continues(self):
        device = FakeDevice()
        session = Session.__new__(Session)
        session.driver = FakeDriver(device)
        session.captcha_solver = None
        session.data = {}
        records = []
        session.record = lambda state, message: records.append((state, message))

        result = session.tick(BackupScreen())

        self.assertEqual(result, "progress")
        self.assertTrue(session.data["backup_restore_skipped"])
        self.assertEqual(session.driver.tapped[0]["text"], "不轉移並繼續")
        self.assertEqual(records[0][0], "backup_restore_skipped")

    def test_backup_restore_screen_is_classified(self):
        root = ET.fromstring(
            '<hierarchy>'
            '<node text="還原或轉移帳戶" enabled="true" bounds="[0,0][100,50]" />'
            '<node text="選擇要還原訊息紀錄和帳戶資料的方式。" enabled="true" bounds="[0,50][100,100]" />'
            '<node text="不轉移並繼續" enabled="true" bounds="[0,100][200,160]" />'
            '</hierarchy>'
        )
        self.assertEqual(Screen(root).kind(), "backup_restore_choice")


if __name__ == "__main__":
    unittest.main(verbosity=2)
