from __future__ import annotations

import base64
import importlib
import json
import shutil
import sys
import tempfile
import time
import unittest
import urllib.parse
import zipfile
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
BYTECODE = PROJECT / "bytecode_project"
sys.path.insert(0, str(BYTECODE))


class FullSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="signal-console-test-", dir=PROJECT.parent))

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_all_recovered_modules_import(self):
        modules = [
            "console.advanced_ui", "console.android", "console.business",
            "console.captcha_extractor", "console.captcha_solver", "console.engine",
            "console.gui", "console.infrastructure", "console.local_secrets",
            "console.param_panel", "console.signal_support.accounts",
            "console.signal_support.device", "console.signal_support.errors",
            "console.signal_support.messaging", "console.signal_support.operations",
            "console.signal_support.profiles", "console.signal_support.registration",
            "console.sms", "console.storage", "console.watchdog",
        ]
        for name in modules:
            with self.subTest(module=name):
                self.assertIsNotNone(importlib.import_module(name))

    def test_storage_schema_settings_queue_logs_and_checkpoints(self):
        from console.storage import Store

        store = Store(self.temp)
        try:
            tables = {row["name"] for row in store.query("SELECT name FROM sqlite_master WHERE type='table'")}
            expected = {
                "settings", "devices", "accounts", "materials", "tasks", "logs",
                "results", "checkpoints", "activations", "schedules", "instances",
            }
            self.assertTrue(expected.issubset(tables))

            store.set_setting("limits", {"register": 2, "friend": 3, "message": 4, "profile": 1})
            self.assertEqual(store.setting("limits")["message"], 4)

            low = store.add_task("check", "serial-a", "+15550000001", {}, priority=1, mode="dry")
            high = store.add_task("register", "serial-b", "+15550000002", {}, priority=9, mode="dry")
            ordered = store.query("SELECT id FROM tasks ORDER BY priority DESC,id")
            self.assertEqual([row["id"] for row in ordered], [high, low])

            store.checkpoint(high, "fixture", {"ok": True})
            self.assertEqual(store.query("SELECT stage FROM checkpoints WHERE task_id=?", (high,))[0]["stage"], "fixture")
            store.log("info", "serial-b", "register", "fixture log")
            self.assertEqual(store.query("SELECT COUNT(*) n FROM logs")[0]["n"], 1)
        finally:
            store.db.close()

    def test_task_results_update_account_counters(self):
        from console.storage import Store, now

        store = Store(self.temp)
        try:
            store.execute(
                "INSERT INTO accounts(phone,serial,created,last_active) VALUES(?,?,?,?)",
                ("+15550000003", "serial-c", now(), now()),
            )
            for kind in ("friend", "message", "profile"):
                ident = store.add_task(kind, "serial-c", "+15550000003", {}, mode="real")
                task = store.query("SELECT * FROM tasks WHERE id=?", (ident,))[0]
                config = {"business_result": {"target": "+15550000004", "message": "fixture", "status": "success"}}
                store.finish_task(task, "done", "", config)
            account = store.query("SELECT * FROM accounts WHERE phone=?", ("+15550000003",))[0]
            self.assertEqual(account["friend_count"], 1)
            self.assertEqual(account["msg_count"], 1)
            self.assertEqual(account["info_modified"], 1)
            self.assertEqual(store.query("SELECT COUNT(*) n FROM results")[0]["n"], 3)
        finally:
            store.db.close()

    def test_csv_and_xlsx_export(self):
        from console.storage import export_table

        rows = [{"phone": "+15550000001", "status": "=formula", "group": "A"}]
        columns = ["phone", "status", "group"]
        csv_path = self.temp / "accounts.csv"
        xlsx_path = self.temp / "accounts.xlsx"
        export_table(csv_path, rows, columns)
        export_table(xlsx_path, rows, columns)
        self.assertIn("'=formula", csv_path.read_text("utf-8-sig"))
        self.assertTrue(zipfile.is_zipfile(xlsx_path))
        with zipfile.ZipFile(xlsx_path) as archive:
            self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())

    def test_phone_files_allocation_and_templates(self):
        from console.signal_support.operations import allocate, load_phones, load_template, normalize_phone, render_message

        phones = self.temp / "phones.txt"
        phones.write_text("+15550000001\n+15550000002\n+15550000001\n", encoding="utf-8")
        loaded = load_phones(phones)
        self.assertEqual(loaded["phones"], ["+15550000001", "+15550000002"])
        self.assertEqual(loaded["duplicates"], 1)
        self.assertEqual(normalize_phone("5550000003", "1"), "+15550000003")
        plan, remaining = allocate(loaded["phones"], ["account-a", "account-b"], 1)
        self.assertEqual(len(plan), 2)
        self.assertEqual(remaining, [])

        template = self.temp / "message.txt"
        template.write_text("Hello {phone} from {account}", encoding="utf-8-sig")
        self.assertEqual(load_template(template), "Hello {phone} from {account}")
        self.assertEqual(render_message(load_template(template), "+1", "A"), "Hello +1 from A")

    def test_profile_asset_folder(self):
        from console.signal_support.operations import profile_assets

        folder = self.temp / "profiles"
        folder.mkdir()
        # Valid 1x1 PNG.
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nWQAAAAASUVORK5CYII="
        )
        (folder / "avatar.png").write_bytes(png)
        (folder / "profiles.csv").write_text("name,image,account\n测试昵称,avatar.png,account-a\n", encoding="utf-8-sig")
        assets = profile_assets(folder)
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["name"], "测试昵称")
        self.assertTrue(Path(assets[0]["image"]).is_file())

    def test_workflow_validation_and_per_kind_limits(self):
        from console.engine import KINDS, validate_workflow

        self.assertTrue({"register", "friend", "message", "profile", "check"}.issubset(KINDS))
        valid = {
            "adapter": "custom",
            "delay_min": 0,
            "delay_max": 1,
            "steps": [
                {"op": "launch", "package": "org.thoughtcrime.securesms"},
                {"op": "assert", "selector": {"text": "Signal"}},
            ],
        }
        validate_workflow(valid, "custom")
        with self.assertRaises(ValueError):
            validate_workflow({**valid, "steps": [{"op": "unsupported"}]}, "custom")

    def test_engine_runs_all_five_business_queues_in_dry_mode(self):
        from console.engine import Engine
        from console.storage import Store

        class FakeAndroid:
            adb = ""
            manager = ""
            def devices(self):
                return [
                    {"serial": f"dry-{i}", "status": "device", "name": f"dry-{i}"}
                    for i in range(5)
                ]

        store = Store(self.temp)
        engine = Engine(store, FakeAndroid())
        try:
            store.set_setting("limits", {
                "register": 2, "friend": 2, "message": 2,
                "profile": 2, "check": 2, "custom": 2,
            })
            store.set_setting("max_devices", 4)
            kinds = ["register", "friend", "message", "profile", "check"]
            for i, kind in enumerate(kinds):
                store.add_task(
                    kind, f"dry-{i}", f"+1555000000{i}",
                    {"adapter": "signal", "variables": {}}, priority=i, mode="dry",
                )
            engine.start()
            deadline = time.time() + 10
            while time.time() < deadline:
                rows = store.query("SELECT kind,state,error FROM tasks ORDER BY id")
                if rows and all(row["state"] == "done" for row in rows):
                    break
                time.sleep(0.1)
            self.assertEqual([row["kind"] for row in rows], kinds)
            self.assertTrue(all(row["state"] == "done" for row in rows), rows)
        finally:
            engine.close()
            store.db.close()

    def test_proxy_and_schedule_helpers(self):
        from console.infrastructure import next_due, validate_proxy

        self.assertEqual(validate_proxy("127.0.0.1:8080"), "127.0.0.1:8080")
        with self.assertRaises(ValueError):
            validate_proxy("http://user:pass@127.0.0.1:8080")
        self.assertIsNotNone(next_due("2026-10-21T00:00:00", 60))

    def test_dpapi_roundtrip(self):
        from console.local_secrets import crypt

        encrypted = crypt("TEST_SECRET_NOT_REAL")
        self.assertNotIn("TEST_SECRET_NOT_REAL", encrypted)
        self.assertEqual(crypt(encrypted, True), "TEST_SECRET_NOT_REAL")

    def test_sms_provider_client_with_fixture_transport(self):
        from console.sms import Grizzly

        replies = {
            "getBalance": "ACCESS_BALANCE:12.34",
            "getStatus": "STATUS_OK:654321",
            "setStatus": "ACCESS_READY",
            "getNumber": "ACCESS_NUMBER:12345:15550000000",
        }

        class Response:
            def __init__(self, value): self.value = value.encode("utf-8")
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _): return self.value

        def transport(request, timeout=0):
            action = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)["action"][0]
            return Response(replies[action])

        client = Grizzly("FIXTURE_KEY", transport=transport, base_url="https://example.invalid/api")
        self.assertIn("12.34", str(client.balance()))
        self.assertEqual(client.status("12345"), "STATUS_OK:654321")
        self.assertEqual(client.set_status("12345", 1), "ACCESS_READY")
        self.assertEqual(client.buy("signal", "1", "1.50")["phone"], "15550000000")

    def test_captcha_repair_module_is_active(self):
        from console.captcha_solver import CaptchaSolver, SignalCaptchaHandler

        class Device:
            def __init__(self): self.calls = []
            def command(self, args, timeout=0, binary=False):
                self.calls.append(args)
                if "resolve-activity" in args:
                    return "org.thoughtcrime.securesms/.CaptchaCallbackActivity"
                return "Status: ok"

        device = Device()
        solver = CaptchaSolver("FIXTURE_KEY")
        solver.solve_hcaptcha = lambda *_args, **_kwargs: {
            "success": True,
            "token": "P1_FIXTURE_TOKEN_abcdefghijklmnopqrstuvwxyz0123456789",
        }
        handler = SignalCaptchaHandler(device, solver)
        handler.extract_hcaptcha_info = lambda: {
            "sitekey": "10000000-ffff-ffff-ffff-000000000001",
            "url": "https://signalcaptchas.org/registration/generate.html",
        }
        result = handler.solve_and_submit()
        self.assertTrue(result["success"])
        self.assertTrue(any(str(x).startswith("signalcaptcha://P1_FIXTURE_TOKEN_") for x in device.calls[1]))

    def test_signal_830_contract_matches_supplied_apk(self):
        from console import signal_contract as contract

        self.assertEqual(contract.VERSION_NAME, "8.30.3")
        self.assertEqual(contract.VERSION_CODE, 176301)
        self.assertEqual(contract.CAPTCHA_CALLBACK_SCHEME, "signalcaptcha://")
        self.assertEqual(contract.CAPTCHA_CALLBACK_PREFIX_LENGTH, 16)
        self.assertFalse(contract.REGISTRATION_ACTIVITY_EXPORTED)
        self.assertFalse(contract.CAPTCHA_CALLBACK_EXPORTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
