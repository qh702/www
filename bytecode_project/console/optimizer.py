"""Runtime reliability and diagnostics for the desktop console.

The module intentionally uses only the Python standard library so it remains
available in the one-file Windows build.  It never records secret values.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def retry_call(
    operation: Callable[[], Any],
    *,
    attempts: int = 3,
    base_delay: float = 0.25,
    max_delay: float = 3.0,
    retry_for: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError, OSError),
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Retry a transient local/network operation with capped exponential delay."""
    attempts = max(1, int(attempts))
    for current in range(1, attempts + 1):
        try:
            return operation()
        except retry_for:
            if current >= attempts:
                raise
            sleep(min(max_delay, base_delay * (2 ** (current - 1))))


def apply_store_optimizations(store: Any) -> dict[str, Any]:
    """Apply safe SQLite settings and indexes for the local concurrent queue."""
    indexes = (
        "CREATE INDEX IF NOT EXISTS idx_tasks_state_priority ON tasks(state,priority DESC,id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_kind_state ON tasks(kind,state,id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_serial_state ON tasks(serial,state,id)",
        "CREATE INDEX IF NOT EXISTS idx_logs_time ON logs(time DESC,id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_logs_kind_time ON logs(kind,time DESC)",
        "CREATE INDEX IF NOT EXISTS idx_results_kind_time ON results(kind,time DESC)",
        "CREATE INDEX IF NOT EXISTS idx_accounts_status_group ON accounts(status,group_name,id)",
        "CREATE INDEX IF NOT EXISTS idx_schedules_due ON schedules(enabled,due)",
    )
    with store.lock:
        store.db.execute("PRAGMA journal_mode=WAL")
        store.db.execute("PRAGMA synchronous=NORMAL")
        store.db.execute("PRAGMA busy_timeout=8000")
        store.db.execute("PRAGMA temp_store=MEMORY")
        store.db.execute("PRAGMA wal_autocheckpoint=500")
        for statement in indexes:
            store.db.execute(statement)
        store.db.commit()
        quick_check = store.db.execute("PRAGMA quick_check").fetchone()[0]
    return {"quick_check": quick_check, "indexes": len(indexes), "busy_timeout_ms": 8000}


def backup_database(store: Any, home: Path, *, keep: int = 7, min_age_hours: int = 24) -> str:
    """Create a consistent SQLite backup, at most once per configured interval."""
    backup_dir = Path(home) / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(backup_dir.glob("console-*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
    if existing and time.time() - existing[0].stat().st_mtime < min_age_hours * 3600:
        return str(existing[0])

    target = backup_dir / datetime.now().strftime("console-%Y%m%d-%H%M%S.sqlite3")
    with store.lock, sqlite3.connect(target) as destination:
        store.db.backup(destination)
    for old in existing[max(0, keep - 1):]:
        try:
            old.unlink()
        except OSError:
            pass
    return str(target)


def _setting_names(store: Any) -> set[str]:
    return {str(row["key"]) for row in store.query("SELECT key FROM settings")}


def collect_health(app: Any, home: Path, database: dict[str, Any], backup: str) -> dict[str, Any]:
    """Return a redacted operational health snapshot suitable for support."""
    home = Path(home)
    store = app.store
    disk = shutil.disk_usage(home)
    names = _setting_names(store)
    counts = {}
    for table in ("devices", "accounts", "tasks", "logs", "results", "schedules", "instances"):
        counts[table] = int(store.query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"])
    states = {row["state"]: row["n"] for row in store.query("SELECT state,COUNT(*) n FROM tasks GROUP BY state")}

    adb = str(getattr(app.android, "adb", "") or "")
    manager = str(getattr(app.android, "manager", "") or "")
    checks = {
        "database_ok": database.get("quick_check") == "ok",
        "data_directory_writable": os.access(home, os.W_OK),
        "disk_free_over_5gb": disk.free >= 5 * 1024**3,
        "adb_configured": bool(adb),
        "adb_exists": bool(adb and Path(adb).is_file()),
        "manager_configured": bool(manager),
        "manager_exists": bool(manager and Path(manager).is_file()),
    }
    score = round(100 * sum(checks.values()) / len(checks)) if checks else 100
    report = {
        "generated_at": _utc_now(),
        "version": "2026.10-optimized",
        "score": score,
        "checks": checks,
        "database": database,
        "backup": backup,
        "disk_free_gb": round(disk.free / 1024**3, 2),
        "counts": counts,
        "task_states": states,
        "configuration_presence": {
            "limits": "limits" in names,
            "max_devices": "max_devices" in names,
            "sms": any("sms" in name.lower() or "grizzly" in name.lower() for name in names),
            "captcha": any("captcha" in name.lower() for name in names),
        },
    }
    report_path = home / "health-latest.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


class RuntimeOptimizer:
    def __init__(self, home: Path):
        self.home = Path(home)

    def apply(self, app: Any) -> dict[str, Any]:
        database = apply_store_optimizations(app.store)
        backup = backup_database(app.store, self.home)
        report = collect_health(app, self.home, database, backup)
        try:
            app.store.log(
                "info",
                "",
                "system",
                f"启动优化完成：数据库 {database['quick_check']}，健康分 {report['score']}",
            )
        except Exception:
            pass
        return report


__all__ = [
    "RuntimeOptimizer", "apply_store_optimizations", "backup_database",
    "collect_health", "retry_call",
]
