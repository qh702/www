from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bytecode_project"))

from console.optimizer import RuntimeOptimizer, retry_call
from console.storage import Store


class OptimizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="optimizer-test-", dir=PROJECT.parent))

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_retry_uses_exponential_delays(self):
        calls, delays = [], []
        def operation():
            calls.append(1)
            if len(calls) < 3:
                raise TimeoutError("fixture")
            return "ok"
        self.assertEqual(retry_call(operation, sleep=delays.append), "ok")
        self.assertEqual(delays, [0.25, 0.5])

    def test_database_indexes_backup_and_redacted_health_report(self):
        store = Store(self.temp / "data")
        class Android:
            adb = ""
            manager = ""
        class App:
            pass
        app = App()
        app.store = store
        app.android = Android()
        try:
            report = RuntimeOptimizer(self.temp).apply(app)
            self.assertEqual(report["database"]["quick_check"], "ok")
            self.assertTrue(Path(report["backup"]).is_file())
            indexes = {row["name"] for row in store.query("SELECT name FROM sqlite_master WHERE type='index'")}
            self.assertIn("idx_tasks_state_priority", indexes)
            saved = json.loads((self.temp / "health-latest.json").read_text("utf-8"))
            self.assertIn("configuration_presence", saved)
            self.assertNotIn("api_key", json.dumps(saved))
        finally:
            store.db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
