"""
Jarvis utilities — timers, reminders, memory, brightness, URLs, news, gaming mode.
"""
import threading
import time
import json
import os
import subprocess
import webbrowser
import urllib.request
import datetime
import ctypes
import tempfile
import numpy as np
import sounddevice as sd
from config import SAMPLE_RATE

# ── Persistent memory (remember / recall) ───────────────────────────

_MEMORY_FILE = os.path.join(os.path.dirname(__file__), ".jarvis_memory.json")
_memory = {}


def _load_memory():
    global _memory
    if os.path.exists(_MEMORY_FILE):
        with open(_MEMORY_FILE, "r", encoding="utf-8") as f:
            _memory = json.load(f)
    return _memory


def _save_memory():
    with open(_MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(_memory, f, indent=2, ensure_ascii=False)


def remember(key, value):
    """Store something in Jarvis's memory."""
    _load_memory()
    _memory[key.lower()] = {"value": value, "time": datetime.datetime.now().isoformat()}
    _save_memory()
    return True


def recall(key=None):
    """Recall something from memory. If no key, return all."""
    _load_memory()
    if key:
        entry = _memory.get(key.lower())
        return entry["value"] if entry else None
    return {k: v["value"] for k, v in _memory.items()}


def forget(key):
    """Remove something from memory."""
    _load_memory()
    if key.lower() in _memory:
        del _memory[key.lower()]
        _save_memory()
        return True
    return False


# ── Timers & Reminders ──────────────────────────────────────────────

_active_timers = {}


def _alarm_sound(duration=2.0):
    """Play an alarm beep."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), dtype=np.float32)
    # Two-tone alarm
    tone = (np.sin(2 * np.pi * 880 * t) * 0.3 +
            np.sin(2 * np.pi * 660 * t * (1 + 0.5 * np.sin(2 * np.pi * 3 * t))) * 0.3
            ).astype(np.float32)
    sd.play(tone, samplerate=SAMPLE_RATE)
    sd.wait()


def set_timer(seconds, label="Timer"):
    """Set a timer. When it fires, plays alarm and speaks."""
    def _fire():
        from speech import speak
        print(f"\n  [timer] {label} — {seconds}s elapsed!")
        _alarm_sound()
        speak(f"Sir, your {label} is up.")
        _active_timers.pop(label, None)

    timer = threading.Timer(seconds, _fire)
    timer.daemon = True
    timer.start()
    _active_timers[label] = {"timer": timer, "seconds": seconds, "set_at": time.time()}
    return True


def set_reminder(seconds, message):
    """Set a reminder with a custom message."""
    def _fire():
        from speech import speak
        print(f"\n  [reminder] {message}")
        _alarm_sound(1.0)
        speak(f"Reminder, sir: {message}")
        _active_timers.pop(message, None)

    timer = threading.Timer(seconds, _fire)
    timer.daemon = True
    timer.start()
    _active_timers[message] = {"timer": timer, "seconds": seconds, "set_at": time.time()}
    return True


def cancel_timer(label=None):
    """Cancel a timer/reminder."""
    if label and label in _active_timers:
        _active_timers[label]["timer"].cancel()
        del _active_timers[label]
        return True
    elif not label and _active_timers:
        for k, v in list(_active_timers.items()):
            v["timer"].cancel()
        _active_timers.clear()
        return True
    return False


# ── URLs & Search ───────────────────────────────────────────────────

def open_url(url):
    """Open a URL in the default browser."""
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return True


def search_google(query):
    """Search Google in the browser."""
    import urllib.parse
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    webbrowser.open(url)
    return True


def search_youtube(query):
    """Search YouTube in the browser."""
    import urllib.parse
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    webbrowser.open(url)
    return True


# ── Screen Brightness ───────────────────────────────────────────────

def set_brightness(level):
    """Set screen brightness (0-100). Works on laptops and some monitors via WMI."""
    level = max(0, min(100, level))
    try:
        subprocess.run(
            ["powershell", "-Command",
             f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
             f".WmiSetBrightness(1,{level})"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            capture_output=True,
        )
        return True
    except Exception:
        return False


# ── News Headlines ──────────────────────────────────────────────────

def get_news(count=5):
    """Get top news headlines from RSS feeds (no API key needed)."""
    try:
        # Use Google News RSS
        url = "https://news.google.com/rss?hl=en&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode("utf-8")

        # Simple XML parsing for titles
        headlines = []
        import re
        items = re.findall(r"<item>.*?<title>(.*?)</title>", content, re.DOTALL)
        for title in items[:count]:
            # Clean HTML entities
            title = title.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
            headlines.append(title)
        return headlines
    except Exception as e:
        print(f"  [news] Error: {e}")
        return []


# ── Gaming Mode ─────────────────────────────────────────────────────

# Apps to close when entering gaming mode
_GAMING_CLOSE = ["discord", "spotify", "google chrome", "firefox", "steam"]
# Apps to keep (whitelist) — user can customize
_GAMING_KEEP = []


def gaming_mode_on():
    """Optimize PC for gaming: close distracting apps, set performance mode."""
    from window_manager import close_app, _find_hwnd

    closed = []
    for app in _GAMING_CLOSE:
        if _find_hwnd(app):
            close_app(app)
            closed.append(app)

    # Set Windows power plan to High Performance
    subprocess.Popen(
        'powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c',
        shell=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )

    return closed


def gaming_mode_off():
    """Restore normal PC mode: balanced power plan."""
    subprocess.Popen(
        'powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e',
        shell=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return True


# ── Shell Command Execution ────────────────────────────────────────

def run_command(command):
    """Run any shell/PowerShell command and return output."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr.strip():
            output += "\n" + result.stderr.strip()
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Error: {e}"


def run_powershell(command):
    """Run a PowerShell command and return output."""
    return run_command(f'powershell -Command "{command}"')


# ── File Operations ────────────────────────────────────────────────

def read_file(path):
    """Read a file's contents."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(10000)  # limit to 10KB
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path, content):
    """Write content to a file."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"  [file] Error: {e}")
        return False


def find_files(query, search_dir=None):
    """Search for files by name pattern."""
    import fnmatch
    if search_dir is None:
        search_dir = os.path.expanduser("~")
    results = []
    try:
        for root, dirs, files in os.walk(search_dir):
            # Skip system/hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                       ("node_modules", "__pycache__", ".git", "AppData")]
            for f in files:
                if query.lower() in f.lower():
                    results.append(os.path.join(root, f))
                    if len(results) >= 20:
                        return results
    except PermissionError:
        pass
    return results


# ── Screen Reading (Screenshot + Vision) ───────────────────────────

def read_screen(question="What's on the screen?"):
    """Take a screenshot and analyze it with Claude Vision."""
    import base64
    from config import ANTHROPIC_API_KEY
    import anthropic

    # Take screenshot
    screenshot_path = os.path.join(tempfile.gettempdir(), "jarvis_screen.png")
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(screenshot_path, "PNG")
    except Exception as e:
        return f"Couldn't capture screen: {e}"

    # Send to Claude Vision
    try:
        with open(screenshot_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_data}},
                    {"type": "text", "text": f"You are Jarvis, a butler AI. Briefly answer: {question}"},
                ],
            }],
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Vision error: {e}"


# ── Mouse & Keyboard Control ──────────────────────────────────────

def type_text(text):
    """Type text using keyboard simulation."""
    try:
        import pyautogui
        pyautogui.typewrite(text, interval=0.02) if text.isascii() else pyautogui.write(text)
        return True
    except ImportError:
        # Fallback to ctypes
        for char in text:
            ctypes.windll.user32.keybd_event(0, 0, 0, 0)
        return False


def press_key(key):
    """Press a key or key combination (e.g. 'ctrl+c', 'enter', 'alt+tab')."""
    try:
        import pyautogui
        if "+" in key:
            keys = [k.strip() for k in key.split("+")]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key)
        return True
    except Exception as e:
        print(f"  [key] Error: {e}")
        return False


def mouse_click(x=None, y=None, button="left"):
    """Click at position. If no position, clicks current location."""
    try:
        import pyautogui
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)
        return True
    except Exception as e:
        print(f"  [mouse] Error: {e}")
        return False


# ── System Info ────────────────────────────────────────────────────

def get_system_info():
    """Get CPU, RAM, disk usage."""
    info = []
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        info.append(f"CPU: {cpu}%")
        info.append(f"RAM: {ram.percent}% ({ram.used // (1024**3)}GB / {ram.total // (1024**3)}GB)")
        info.append(f"Disk C: {disk.percent}% ({disk.free // (1024**3)}GB free)")
    except ImportError:
        # Fallback without psutil
        result = run_command('wmic cpu get loadpercentage /value')
        info.append(result)
    return " | ".join(info)


# ── Clipboard ──────────────────────────────────────────────────────

def get_clipboard():
    """Read current clipboard text."""
    try:
        ctypes.windll.user32.OpenClipboard(0)
        handle = ctypes.windll.user32.GetClipboardData(13)  # CF_UNICODETEXT
        if handle:
            text = ctypes.wstring_at(handle)
            ctypes.windll.user32.CloseClipboard()
            return text
        ctypes.windll.user32.CloseClipboard()
        return "(clipboard empty)"
    except Exception:
        return "(couldn't read clipboard)"


def set_clipboard(text):
    """Set clipboard text."""
    try:
        subprocess.run(
            ["powershell", "-Command", f"Set-Clipboard -Value '{text}'"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True
    except Exception:
        return False


# ── Daily Morning Greeting ─────────────────────────────────────────

_LAST_GREETING_FILE = os.path.join(os.path.dirname(__file__), ".jarvis_last_greeting")


def is_new_day():
    """Check if this is the first launch of the day."""
    today = datetime.date.today().isoformat()
    if os.path.exists(_LAST_GREETING_FILE):
        with open(_LAST_GREETING_FILE, "r") as f:
            last = f.read().strip()
        if last == today:
            return False
    with open(_LAST_GREETING_FILE, "w") as f:
        f.write(today)
    return True


def get_real_madrid_news(count=5):
    """Get Real Madrid news from Google News RSS."""
    try:
        import re as _re
        query = "Real+Madrid"
        url = f"https://news.google.com/rss/search?q={query}&hl=en&gl=ES&ceid=ES:en"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode("utf-8")
        headlines = []
        items = _re.findall(r"<item>.*?<title>(.*?)</title>", content, _re.DOTALL)
        for title in items[:count]:
            title = title.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
            headlines.append(title)
        return headlines
    except Exception as e:
        print(f"  [news] Real Madrid news error: {e}")
        return []


def generate_morning_greeting():
    """Use Claude to generate a personalized morning greeting with Real Madrid news."""
    from config import ANTHROPIC_API_KEY
    import anthropic

    headlines = get_real_madrid_news(5)
    news_text = "\n".join(f"- {h}" for h in headlines) if headlines else "No headlines available."

    _load_memory()
    memories = {k: v["value"] for k, v in _memory.items()}

    now = datetime.datetime.now()
    time_str = now.strftime("%I:%M %p")
    day_str = now.strftime("%A, %B %d")

    prompt = f"""You are Jarvis, a British AI butler. Generate a warm morning greeting for your boss Dani (Daniel Madrid).

INFO ABOUT DANI: {json.dumps(memories)}
TODAY: {day_str}, {time_str}
REAL MADRID NEWS:
{news_text}

Rules:
- Greet him warmly, mention the day/time briefly
- Summarize 1-2 key Real Madrid headlines in a natural, conversational way
- End by asking if he'd like to hear more details or if there's anything he needs
- Keep it under 4 sentences total
- Be warm but concise — butler style"""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"  [greeting] Claude error: {e}")
        if headlines:
            return f"Good morning, sir. Latest on Real Madrid: {headlines[0]}. Shall I fill you in on the details?"
        return "Good morning, Dani. Ready to assist whenever you need me, sir."
