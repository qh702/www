from __future__ import annotations

import shutil
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bytecode_project"))

from console.gui import App
from console.optimizer import RuntimeOptimizer
from console.ui_optimizer import UIEnhancer, _sync_captcha_runtime, install_ui_optimizations


class UIOptimizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="ui-test-", dir=PROJECT.parent))

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_enhanced_gui_builds_and_has_menu_shortcuts_and_state(self):
        install_ui_optimizations(App)
        root = tk.Tk()
        root.withdraw()
        app = App(root, self.temp)
        health = RuntimeOptimizer(self.temp).apply(app)
        enhancer = UIEnhancer(app, root, self.temp, health)
        enhancer.apply()
        try:
            root.update_idletasks()
            self.assertEqual(len(app.pages), 13)
            self.assertTrue(str(root.cget("menu")))
            self.assertTrue(root.bind_class("all", "<F5>"))
            self.assertTrue(root.bind_class("all", "<Control-k>"))
            enhancer._save_state()
            self.assertTrue((self.temp / "ui-state.json").is_file())
        finally:
            app.engine.close()
            app.store.db.close()
            root.destroy()

    def test_saved_captcha_key_enables_runtime_and_persists_flag(self):
        install_ui_optimizations(App)
        root = tk.Tk()
        root.withdraw()
        app = App(root, self.temp)
        try:
            app.captcha_key.set("FIXTURE_KEY_NOT_SENT")
            enabled = _sync_captcha_runtime(app, persist=True)
            self.assertTrue(enabled)
            self.assertTrue(app.engine.captcha_enabled)
            self.assertEqual(app.engine.captcha_key, "FIXTURE_KEY_NOT_SENT")
            self.assertEqual(app.store.setting("captcha_enabled"), "是")
        finally:
            app.engine.close()
            app.store.db.close()
            root.destroy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
