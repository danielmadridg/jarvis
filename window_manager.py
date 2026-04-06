"""
Multi-monitor window management via Win32 API.
  - Detect monitors and sort by physical position
  - Launch applications
  - Move / maximise windows on a target monitor
"""
import os
import subprocess
import time
import ctypes
import ctypes.wintypes
from config import APPS

# ── Win32 constants ──────────────────────────────────────────────────
SW_RESTORE = 9
SW_MAXIMIZE = 3
SWP_NOZORDER = 0x0004

user32 = ctypes.windll.user32


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
    ]


# ── Monitor detection ────────────────────────────────────────────────

def get_monitors():
    """Return monitors sorted top→bottom then left→right."""
    monitors = []

    def _cb(hMon, hdc, lprc, lParam):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hMon, ctypes.byref(info))
        r = info.rcWork
        monitors.append({
            "x": r.left, "y": r.top,
            "w": r.right - r.left,
            "h": r.bottom - r.top,
        })
        return True

    CMPFUNC = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.wintypes.HMONITOR,
        ctypes.wintypes.HDC,
        ctypes.POINTER(ctypes.wintypes.RECT),
        ctypes.wintypes.LPARAM,
    )
    user32.EnumDisplayMonitors(None, None, CMPFUNC(_cb), 0)
    monitors.sort(key=lambda m: (m["y"], m["x"]))
    return monitors


def print_monitors():
    mons = get_monitors()
    print(f"  [monitors] {len(mons)} detectados:")
    for i, m in enumerate(mons):
        print(f"    [{i}] {m['w']}x{m['h']}  pos ({m['x']},{m['y']})")
    print()


# ── App launch ───────────────────────────────────────────────────────

def open_app(app_name):
    """Launch an app from the registry. Supports .lnk, .url, .exe shortcuts."""
    cfg = APPS.get(app_name)
    if not cfg:
        print(f"  [launch] App desconocida: {app_name}")
        return False

    try:
        if "shortcut" in cfg:
            # .lnk / .url / .exe from C:\ALL\Shortcuts
            os.startfile(cfg["shortcut"])
        elif "protocol" in cfg:
            subprocess.Popen(
                ["cmd", "/c", "start", "", cfg["protocol"]],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            cmd = cfg["path"]
            args = cfg.get("args", "")
            subprocess.Popen(
                f'"{cmd}" {args}',
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        return True
    except Exception as e:
        print(f"  [launch] Error abriendo {app_name}: {e}")
        return False


# ── Window finder ────────────────────────────────────────────────────

kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


def _get_process_name(hwnd):
    """Get the .exe name of the process that owns *hwnd*."""
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value)
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(260)
    psapi.GetModuleBaseNameW(h, None, buf, 260)
    kernel32.CloseHandle(h)
    return buf.value.lower()


def _find_hwnd(app_name):
    """
    Find a visible window by matching against:
      1. Process name (spotify.exe, discord.exe, etc.)
      2. Window title
    This handles apps like Spotify whose title is the song name.
    """
    hint = app_name.lower()
    result = []

    def _cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if not length:
                return True

            # Check process name first (most reliable)
            proc = _get_process_name(hwnd)
            if hint in proc:
                result.append(hwnd)
                return True

            # Fallback: check window title
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if hint in buf.value.lower():
                result.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM,
    )
    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return result[0] if result else None


# ── Move window to monitor ───────────────────────────────────────────

def move_to_monitor(app_name, monitor_index, retries=25):
    """
    Wait for the app window to appear, then move + maximise it on
    the given monitor.  Runs in a thread (non-blocking from caller).
    """
    monitors = get_monitors()
    if monitor_index >= len(monitors):
        print(f"  [move] Monitor {monitor_index} no existe ({len(monitors)} disponibles)")
        return False

    mon = monitors[monitor_index]

    hwnd = None
    for _ in range(retries):
        hwnd = _find_hwnd(app_name)
        if hwnd:
            break
        time.sleep(0.25)

    if not hwnd:
        print(f"  [move] No encontré ventana de {app_name}")
        return False

    # Restore in case it's minimised
    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.2)

    # Position on target monitor
    user32.SetWindowPos(
        hwnd, 0,
        mon["x"] + 1, mon["y"] + 1, mon["w"] - 2, mon["h"] - 2,
        SWP_NOZORDER,
    )
    time.sleep(0.1)
    user32.ShowWindow(hwnd, SW_MAXIMIZE)
    time.sleep(0.2)
    # Second maximize ensures it sticks (some apps ignore the first)
    user32.ShowWindow(hwnd, SW_MAXIMIZE)
    print(f"  [move] {app_name} -> monitor {monitor_index}")
    return True


def close_app(app_name):
    hwnd = _find_hwnd(app_name)
    if hwnd:
        WM_CLOSE = 0x0010
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True
    return False


# ── System commands ──────────────────────────────────────────────────

def shutdown_pc(delay=5):
    """Shutdown in *delay* seconds (gives time to cancel with `shutdown /a`)."""
    subprocess.Popen(f"shutdown /s /t {delay}", shell=True)


def restart_pc(delay=5):
    subprocess.Popen(f"shutdown /r /t {delay}", shell=True)


def sleep_pc():
    # rundll32 method works without admin
    subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)


def lock_pc():
    user32.LockWorkStation()


def cancel_shutdown():
    subprocess.Popen("shutdown /a", shell=True)


def set_volume(level):
    """Set system volume to *level* (0-100) using nircmd if available, else PowerShell."""
    # Use PowerShell as universal fallback
    normalized = max(0, min(100, level)) / 100.0
    ps = (
        f'$vol = [Audio.Volume]::New(); '
        f'(New-Object -ComObject WScript.Shell).SendKeys([char]173); '  # mute toggle trick
    )
    # Simpler: use nircmd or fall back to key simulation
    # Send volume-down keys to zero, then volume-up to target
    subprocess.Popen(
        f'powershell -Command "'
        f'$wsh = New-Object -ComObject WScript.Shell; '
        f'1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }}; '  # 50× vol down = 0
        f'1..{level // 2} | ForEach-Object {{ $wsh.SendKeys([char]175) }}'  # vol up
        f'"',
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def mute_volume():
    subprocess.Popen(
        'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"',
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def minimize_all():
    """Win+D — show desktop / minimise everything."""
    user32.keybd_event(0x5B, 0, 0, 0)  # Win down
    user32.keybd_event(0x44, 0, 0, 0)  # D down
    user32.keybd_event(0x44, 0, 2, 0)  # D up
    user32.keybd_event(0x5B, 0, 2, 0)  # Win up


def _key_tap(vk, delay=0.05):
    """Tap a virtual key."""
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)
    time.sleep(delay)


def _clipboard_paste(text):
    """Copy text to clipboard and paste with Ctrl+V."""
    # Set clipboard via Win32
    CF_UNICODETEXT = 13
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.restype = ctypes.c_void_p

    user32.OpenClipboard(0)
    user32.EmptyClipboard()
    data = text.encode("utf-16-le") + b"\x00\x00"
    h = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    p = kernel32.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    kernel32.GlobalUnlock(h)
    user32.SetClipboardData(CF_UNICODETEXT, h)
    user32.CloseClipboard()

    # Ctrl+V
    time.sleep(0.1)
    user32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
    user32.keybd_event(0x56, 0, 0, 0)  # V down
    user32.keybd_event(0x56, 0, 2, 0)  # V up
    user32.keybd_event(0x11, 0, 2, 0)  # Ctrl up


def play_spotify(query):
    """Search and play a song/artist/playlist on Spotify."""
    # Make sure Spotify is running
    hwnd = _find_hwnd("spotify")
    if not hwnd:
        open_app("spotify")
        time.sleep(4)
        hwnd = _find_hwnd("spotify")

    if not hwnd:
        print("  [spotify] Could not find Spotify window")
        return False

    # Focus Spotify
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)

    # Ctrl+K to focus search bar
    user32.keybd_event(0x11, 0, 0, 0)
    user32.keybd_event(0x4B, 0, 0, 0)
    user32.keybd_event(0x4B, 0, 2, 0)
    user32.keybd_event(0x11, 0, 2, 0)
    time.sleep(0.4)

    # Select all + paste query from clipboard
    user32.keybd_event(0x11, 0, 0, 0)  # Ctrl+A
    user32.keybd_event(0x41, 0, 0, 0)
    user32.keybd_event(0x41, 0, 2, 0)
    user32.keybd_event(0x11, 0, 2, 0)
    time.sleep(0.1)

    _clipboard_paste(query)
    time.sleep(0.3)

    # Press Enter to search
    _key_tap(0x0D, 0.1)

    # Wait for search results to load
    time.sleep(2.5)

    # Navigate to top result and play: Enter on the top result
    _key_tap(0x0D, 0.1)

    print(f"  [spotify] Searching and playing: {query}")
    return True


def take_screenshot():
    """Win+Shift+S — snipping tool."""
    user32.keybd_event(0x5B, 0, 0, 0)   # Win
    user32.keybd_event(0xA0, 0, 0, 0)   # Shift
    user32.keybd_event(0x53, 0, 0, 0)   # S
    user32.keybd_event(0x53, 0, 2, 0)
    user32.keybd_event(0xA0, 0, 2, 0)
    user32.keybd_event(0x5B, 0, 2, 0)
