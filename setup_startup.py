"""
Adds (or removes) Jarvis from Windows startup via Task Scheduler.
Runs with high priority at logon, BEFORE the Startup folder.

Usage:
  python setup_startup.py          # install
  python setup_startup.py remove   # uninstall
"""
import os
import sys
import subprocess

TASK_NAME = "JarvisAssistant"
JARVIS_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_PY = os.path.join(JARVIS_DIR, "main.py")
BAT_PATH = os.path.join(JARVIS_DIR, "start_jarvis.bat")
VBS_PATH = os.path.join(JARVIS_DIR, "start_jarvis.vbs")
LOG_PATH = os.path.join(JARVIS_DIR, "jarvis.log")
STARTUP_DIR = os.path.join(
    os.environ["APPDATA"],
    "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
)
OLD_VBS_PATH = os.path.join(STARTUP_DIR, "Jarvis.vbs")


def install():
    python_exe = sys.executable.replace("pythonw", "python")

    # Remove old Startup folder method if it exists
    if os.path.exists(OLD_VBS_PATH):
        os.remove(OLD_VBS_PATH)
        print("[cleanup] Removed old Startup folder entry.")

    # Create batch file
    bat_content = (
        f'@echo off\n'
        f'chcp 65001 >nul\n'
        f'set PYTHONIOENCODING=utf-8\n'
        f'cd /d "{JARVIS_DIR}"\n'
        f'"{python_exe}" "{MAIN_PY}" >> "{LOG_PATH}" 2>&1\n'
    )
    with open(BAT_PATH, "w") as f:
        f.write(bat_content)

    # Create VBS wrapper (hidden window)
    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        f'WshShell.Run """{BAT_PATH}""", 0, False\n'
    )
    with open(VBS_PATH, "w") as f:
        f.write(vbs_content)

    # Delete old task if exists
    subprocess.run(
        f'schtasks /Delete /TN "{TASK_NAME}" /F',
        shell=True, capture_output=True,
    )

    # Create scheduled task with high priority at logon
    # /RL HIGHEST = run with highest privileges
    # /DELAY 0000:05 = 5 second delay to let audio devices init
    result = subprocess.run(
        f'schtasks /Create /TN "{TASK_NAME}" '
        f'/TR "wscript.exe \\"{VBS_PATH}\\"" '
        f'/SC ONLOGON '
        f'/RL HIGHEST '
        f'/DELAY 0000:05 '
        f'/F',
        shell=True, capture_output=True, text=True,
    )

    if result.returncode == 0:
        print(f"[OK] Jarvis se iniciara con Windows (prioridad alta, Task Scheduler).")
        print(f"     Task:  {TASK_NAME}")
        print(f"     Batch: {BAT_PATH}")
        print(f"     Log:   {LOG_PATH}")
        print(f"     Delay: 5s (para que el audio este listo)")
    else:
        print(f"[ERROR] No se pudo crear la tarea: {result.stderr.strip()}")
        print(f"  Intenta ejecutar como administrador:")
        print(f"  python setup_startup.py")


def remove():
    result = subprocess.run(
        f'schtasks /Delete /TN "{TASK_NAME}" /F',
        shell=True, capture_output=True, text=True,
    )
    # Also clean up old Startup folder entry
    if os.path.exists(OLD_VBS_PATH):
        os.remove(OLD_VBS_PATH)

    if result.returncode == 0:
        print("[OK] Jarvis eliminado del inicio automatico.")
    else:
        print("[--] No estaba instalado en el inicio.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "remove":
        remove()
    else:
        install()
