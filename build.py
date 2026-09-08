from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "app.py"
DIST = ROOT
WORK = ROOT / "build_tmp"

if not SRC.is_file():
    raise SystemExit(f"ERROR: source not found: {SRC}")

try:
    import PyInstaller.__main__
except ImportError:
    raise SystemExit("ERROR: PyInstaller is not installed.")

# Remove stale artifacts from previous attempts.
for path in (ROOT / "HiBinds.exe", WORK):
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)

args = [
    str(SRC),
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--name", "HiBinds",
    "--distpath", str(DIST),
    "--workpath", str(WORK),
    "--specpath", str(WORK),
    "--collect-all", "customtkinter",
    "--paths", str(ROOT / "src"),
]

print("HiBinds EXE Builder")
print("Source:", SRC)
print("Output:", ROOT / "HiBinds.exe")
print()

try:
    PyInstaller.__main__.run(args)
finally:
    shutil.rmtree(WORK, ignore_errors=True)
    # PyInstaller spec is placed in WORK by --specpath; remove it with WORK.

exe = ROOT / "HiBinds.exe"
if not exe.is_file():
    raise SystemExit("ERROR: build finished but HiBinds.exe was not created.")

print()
print("BUILD SUCCESS")
print("EXE:", exe)
print("SIZE:", exe.stat().st_size, "bytes")
