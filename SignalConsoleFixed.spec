# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

root = Path(SPECPATH)
src = root / "bytecode_project"

a = Analysis(
    [str(src / "launcher.py")],
    pathex=[str(src)],
    binaries=[],
    datas=[
        (str(src / "console" / "captcha_solver.pyc"), "console"),
        (str(src / "console" / "signal_support" / "registration.pyc"), "console/signal_support"),
    ],
    hiddenimports=[
        "console.advanced_ui", "console.android", "console.business",
        "console.captcha_extractor", "console.captcha_solver", "console.engine",
        "console.gui", "console.infrastructure", "console.local_secrets",
        "console.param_panel", "console.signal_support.accounts",
        "console.signal_support.device", "console.signal_support.errors",
        "console.signal_support.messaging", "console.signal_support.operations",
        "console.signal_support.profiles", "console.signal_support.registration",
        "console.sms", "console.storage", "console.watchdog",
        "PIL.Image", "PIL.ImageTk", "requests",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SignalConsoleFixed",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
