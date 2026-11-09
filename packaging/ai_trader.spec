import os

ROOT = os.path.dirname(SPECPATH)
from PyInstaller.utils.hooks import collect_all


datas = [
    (os.path.join(ROOT, "ui/index.html"), "ui"),
    (os.path.join(ROOT, "examples/synthetic_5m.csv"), "examples"),
]
binaries = []
hiddenimports = []
for package in ("webview", "keyring"):
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports

a = Analysis(
    [os.path.join(ROOT, "desktop.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI Trader",
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(ROOT, "assets/app_icon.icns"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="AI Trader")
app = BUNDLE(
    coll,
    name="AI Trader.app",
    icon=os.path.join(ROOT, "assets/app_icon.icns"),
    bundle_identifier="com.go-minseong.aitrader",
    info_plist={
        "CFBundleDisplayName": "AI Trader",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
        "LSMinimumSystemVersion": "12.0",
        "LSUIElement": False,
        "NSHighResolutionCapable": True,
    },
)
