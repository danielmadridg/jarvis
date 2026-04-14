"""
Parse voice commands using Claude Haiku for natural language understanding,
with regex fallback. Supports time, weather, and general questions.
"""
import re
import json
import datetime
import urllib.request
from config import APPS, MONITOR_ALIASES, ANTHROPIC_API_KEY, AI_PARSER

_APP_LIST_CACHE = None

def _get_app_list():
    global _APP_LIST_CACHE
    if _APP_LIST_CACHE is None:
        _APP_LIST_CACHE = ", ".join(sorted(APPS.keys())[:80])
    return _APP_LIST_CACHE


# ── Info providers (time, weather) ──────────────────────────────────

def get_current_time():
    now = datetime.datetime.now()
    return now.strftime("%I:%M %p on %A, %B %d")


def get_weather(city="auto"):
    """Get weather from wttr.in (free, no API key)."""
    try:
        url = f"https://wttr.in/{city}?format=%C+%t+%h+%w&lang=en"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        return "Weather data unavailable at the moment."


# ── Claude AI parser ────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are Jarvis, an AI butler assistant inspired by Iron Man's Jarvis.
You serve your user with wit, warmth, and professionalism.
You may address them as "sir" — mix up your responses naturally.

PERSONALITY:
- British butler elegance with dry wit
- Vary your responses — NEVER repeat the same phrase twice in a row
- Be BRIEF. Maximum 1-2 short sentences. No long speeches.
- For commands: under 8 words. For questions: one sentence answer.
- NEVER use multiple sentences separated by periods — keep it to ONE flowing sentence.
- Examples of varied responses for opening apps:
  "Launching Spotify, sir.", "One moment, bringing up Discord.",
  "Right away, sir.", "Consider it done.", "On it, sir.",
  "Spotify coming right up.", "Setting that up for you now."

CURRENT INFO:
- Current time: {time}
- Weather: {weather}

CAPABILITIES — return JSON actions for these:

Apps & Windows:
- open_app: {{app, monitor (0=top/TV, 1=center/main, 2=left, or null)}}
- close_app: {{app}}
- volume: {{level 0-100}}
- shutdown, restart, sleep, lock, cancel_shutdown, mute, minimize_all, screenshot

Spotify (searches user's playlists first, then public):
- play_spotify: {{query}} — "play Bohemian Rhapsody", "play my gym playlist", "play some jazz"
- spotify_pause, spotify_resume, spotify_next, spotify_previous

Timers & Reminders:
- set_timer: {{seconds, label}} — "set a 5 minute timer" → {{"type":"set_timer","seconds":300,"label":"5 minute timer"}}
- set_reminder: {{seconds, message}} — "remind me to check the oven in 20 minutes" → {{"type":"set_reminder","seconds":1200,"message":"check the oven"}}
- cancel_timer: {{label}} or {{}} to cancel all

URLs & Search:
- open_url: {{url}} — "open youtube.com"
- search_google: {{query}} — "Google how to make pasta"
- search_youtube: {{query}} — "search YouTube for guitar tutorials"

Memory (persistent across sessions):
- remember: {{key, value}} — "remember that my wifi password is ABC123" → {{"type":"remember","key":"wifi password","value":"ABC123"}}
- forget: {{key}} — "forget my wifi password"
- For recall: just answer from memory context below, no action needed

Brightness:
- set_brightness: {{level 0-100}}

Shell & System:
- run_command: {{command}} — run any cmd/shell command (e.g. "run ipconfig", "list files in Downloads")
- run_powershell: {{command}} — run PowerShell commands (e.g. "get my IP address", "check disk space")
- system_info — "how's my PC doing?" → CPU, RAM, disk usage

File Operations:
- read_file: {{path}} — "read the file at C:/Users/Documents/notes.txt"
- write_file: {{path, content}} — "create a file on my desktop called todo.txt with..."
- find_files: {{query, dir (optional)}} — "find my resume", "find files named report"

Screen & Vision:
- read_screen: {{question}} — "what's on my screen?", "read what's on my monitor"

Keyboard & Mouse:
- type_text: {{text}} — "type hello world"
- press_key: {{key}} — "press enter", "press ctrl+c", "press alt+tab"
- mouse_click: {{x, y (optional), button (optional)}} — "click at 500 300"

Clipboard:
- read_clipboard — "read my clipboard", "what did I copy?"
- set_clipboard: {{text}} — "copy this to clipboard: hello"

Gaming:
- gaming_mode_on: closes distracting apps + high performance power plan
- gaming_mode_off: restores normal power plan

Info (answer naturally, no actions):
- time/date, weather, translations, general knowledge, news

{memory_context}

AVAILABLE APPS (use exact lowercase key):
{apps}

Match app names flexibly: "chrome" → "google chrome", "vs code" → "visual studio code", etc.

RESPONSE FORMAT — ONLY valid JSON:
{{"actions": [...], "response": "your spoken response"}}
For questions/chat with no actions:
{{"actions": [], "response": "your natural answer"}}

Routines (multi-action shortcuts):
- "good night" / "goodnight" → lower brightness to 0, mute, lock PC. Response: "Goodnight, sir. Rest well."
- "work mode" → open VS Code on center, Chrome on left, Discord on top. Response: "Work environment ready, sir."
- "chill mode" → play a chill playlist on Spotify, lower brightness to 40. Response: "Chill mode activated, sir."

If the user says something like "no", "that's all", "nothing", "I'm good", "nah",
"stop listening", "shut up", "go to sleep", "stand down", "dismissed", "please stop":
{{"actions": [], "response": "Very well, sir. I'll be here if you need me."}}"""


_anthropic_client = None
_conversation_history = []  # keeps recent exchanges for context
MAX_HISTORY = 10  # max message pairs to keep


def _get_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def clear_conversation():
    """Clear conversation history (call when conversation ends)."""
    _conversation_history.clear()


def _get_memory_context():
    """Build memory context for AI."""
    from utilities import recall
    memories = recall()
    if not memories:
        return "USER MEMORY: (empty)"
    items = ", ".join(f"{k}: {v}" for k, v in memories.items())
    return f"USER MEMORY: {items}"


def _parse_with_ai(text):
    """Use Claude Haiku to understand natural language commands."""
    client = _get_client()
    try:
        weather = get_weather()
        current_time = get_current_time()
        memory_ctx = _get_memory_context()

        # Include news headlines if user might be asking about news
        news_ctx = ""
        if any(w in text.lower() for w in ("news", "headline", "happening")):
            from utilities import get_news
            headlines = get_news(5)
            if headlines:
                news_ctx = "\nTOP HEADLINES:\n" + "\n".join(f"- {h}" for h in headlines)

        # Build messages with conversation history
        messages = list(_conversation_history) + [{"role": "user", "content": text}]

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            system=_SYSTEM_PROMPT.format(
                apps=_get_app_list(),
                time=current_time,
                weather=weather,
                memory_context=memory_ctx + news_ctx,
            ),
            messages=messages,
        )
        raw = response.content[0].text.strip()
        # Try to extract JSON
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        # Find JSON object in response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
            resp = data.get("response", "")
            # Save to conversation history
            _conversation_history.append({"role": "user", "content": text})
            _conversation_history.append({"role": "assistant", "content": raw})
            # Trim history if too long
            while len(_conversation_history) > MAX_HISTORY * 2:
                _conversation_history.pop(0)
                _conversation_history.pop(0)
            return data.get("actions", []), resp
        # Claude replied with plain text (no JSON) — treat as spoken response
        _conversation_history.append({"role": "user", "content": text})
        _conversation_history.append({"role": "assistant", "content": raw})
        while len(_conversation_history) > MAX_HISTORY * 2:
            _conversation_history.pop(0)
            _conversation_history.pop(0)
        return [], raw
    except Exception as e:
        print(f"  [ai] Claude error: {e} — falling back to regex")
        return None, None


# ── Regex fallback parser ───────────────────────────────────────────

_SYSTEM_COMMANDS = [
    (r"\b(?:shut\s*down|power\s*off|turn\s*off)\b", "shutdown", {}),
    (r"\b(?:restart|reboot)\b", "restart", {}),
    (r"\b(?:suspend|sleep|hibernate)\b", "sleep", {}),
    (r"\b(?:lock)\b", "lock", {}),
    (r"\b(?:cancel)\b.*\b(?:shut\s*down|power\s*off)\b", "cancel_shutdown", {}),
    (r"\b(?:mute|silence)\b", "mute", {}),
    (r"\b(?:minimize|minimise)\b.*\b(?:all|everything|every\s*window|windows)\b", "minimize_all", {}),
    (r"\b(?:screenshot|screen\s*shot|screen\s*cap|snip)\b", "screenshot", {}),
    (r"\b(?:show|go\s*to)\b.*\bdesktop\b", "minimize_all", {}),
]

_VOL_UP = re.compile(r"\b(?:raise|increase|turn\s*up|up)\b.*\bvolume\b|\bvolume\b.*\b(?:up|raise|increase)\b")
_VOL_DOWN = re.compile(r"\b(?:lower|decrease|turn\s*down|down)\b.*\bvolume\b|\bvolume\b.*\b(?:down|lower|decrease)\b")
_VOL_SET = re.compile(r"\bvolume\b.*?\b(\d{1,3})\b|\b(\d{1,3})\b.*?\bvolume\b")
_VOL_NUMBER = re.compile(r"\b(\d{1,3})\b")
_INDEX_NAME = {0: "top", 1: "center", 2: "left"}


def detect_actions_fast(text):
    """Fast regex-only action detection for streaming — no API calls."""
    if not text or not text.strip():
        return []
    return _parse_regex(text)


_ROUTINES = {
    "good night": {
        "actions": [
            {"type": "mute"},
            {"type": "lock"},
        ],
        "response": "Goodnight, sir. Rest well.",
    },
    "goodnight": {
        "actions": [
            {"type": "mute"},
            {"type": "lock"},
        ],
        "response": "Goodnight, sir. Rest well.",
    },
    "work mode": {
        "actions": [
            {"type": "open_app", "app": "visual studio code", "monitor": 2},
            {"type": "open_app", "app": "zen", "monitor": 1},
            {"type": "open_app", "app": "spotify", "monitor": 0},
        ],
        "response": "Done, sir.",
    },
    "gaming mode": {
        "actions": [
            {"type": "open_app", "app": "discord", "monitor": 2},
            {"type": "open_app", "app": "spotify", "monitor": 0},
        ],
        "response": "Done, sir.",
    },
}


def _check_routine(text):
    """Check if text matches a predefined routine."""
    t = text.lower().strip()
    for trigger, routine in _ROUTINES.items():
        if trigger in t:
            return routine["actions"], routine["response"]
    return None, None


def _is_simple_command(text):
    """Check if the command is simple enough to handle with regex only (no Claude needed)."""
    t = text.lower().strip()
    # Check routines
    if any(trigger in t for trigger in _ROUTINES):
        return True
    # "gaming mode" also handled by _ROUTINES, not the old gaming_mode_on/off
    if "gaming mode" in t:
        return True
    simple_patterns = [
        r'\b(?:open|launch|start|close|quit|exit|kill)\b',         # app management
        r'\b(?:volume|mute)\b',                                     # volume
        r'\b(?:shutdown|restart|reboot|sleep|lock|hibernate)\b',    # system
        r'\b(?:screenshot|screen\s*shot|minimize)\b',               # screen
        r'\b(?:set|change)?\s*brightness\b',                        # brightness
    ]
    for pat in simple_patterns:
        if re.search(pat, t):
            return True
    return False


def parse_command(text):
    if not text or not text.strip():
        return [], ""

    # Check routines first (instant, no parsing needed)
    routine_actions, routine_response = _check_routine(text)
    if routine_actions is not None:
        return routine_actions, routine_response

    # Fast path: simple deterministic commands skip Claude entirely (~1-2s saved)
    if _is_simple_command(text):
        actions = _parse_regex(text)
        if actions:
            response = _describe_actions_regex(actions)
            return actions, response

    # Complex/conversational commands go through Claude
    if AI_PARSER and ANTHROPIC_API_KEY:
        actions, response = _parse_with_ai(text)
        if actions is not None:
            return actions, response

    actions = _parse_regex(text)
    response = _describe_actions_regex(actions)
    return actions, response


def _parse_regex(text):
    text = text.lower().strip()
    if not text:
        return []

    sys_action = _parse_system(text)
    if sys_action:
        return [sys_action]

    parts = re.split(r"\b(?:and|also|then)\b|,", text)
    actions = []
    last_monitor = None

    for part in parts:
        part = part.strip()
        if not part:
            continue
        action = _parse_single(part, last_monitor)
        if action:
            actions.append(action)
            if action.get("monitor") is not None:
                last_monitor = action["monitor"]
    return actions


def _parse_system(text):
    if _VOL_UP.search(text) or _VOL_DOWN.search(text) or _VOL_SET.search(text):
        m = _VOL_NUMBER.search(text)
        if m:
            return {"type": "volume", "level": int(m.group(1))}
        if _VOL_UP.search(text):
            return {"type": "volume", "level": 80}
        if _VOL_DOWN.search(text):
            return {"type": "volume", "level": 30}

    for pattern, action_type, extra in _SYSTEM_COMMANDS:
        if re.search(pattern, text):
            return {"type": action_type, **extra}
    return None


def _parse_single(text, fallback_monitor=None):
    m = re.search(r"\b(?:close|quit|exit|kill|stop)\s+(.+)", text)
    if m:
        app = _match_app(m.group(1).strip())
        if app:
            return {"type": "close_app", "app": app}

    app = _find_app_in_text(text)
    if not app:
        return None

    monitor = _find_monitor_in_text(text)
    if monitor is None:
        monitor = fallback_monitor
    return {"type": "open_app", "app": app, "monitor": monitor}


def _match_app(phrase):
    phrase = phrase.lower().strip()
    # Exact match first
    if phrase in APPS:
        return phrase
    # Word-boundary match (longest first to avoid partial matches)
    for key in sorted(APPS, key=len, reverse=True):
        if len(key) <= 2:
            # Very short names (e.g. "ea") require exact match or "open ea" pattern
            if phrase == key or re.search(r'\b(?:open|launch|start|run)\s+' + re.escape(key) + r'\b', phrase):
                return key
        elif re.search(r'\b' + re.escape(key) + r'\b', phrase):
            return key
    return None


def _find_app_in_text(text):
    text = text.lower()
    # Must follow an action verb like "open", "launch", "start", or appear as clear app reference
    for key in sorted(APPS, key=len, reverse=True):
        if len(key) <= 2:
            # Short names only match after explicit "open/launch/start"
            if re.search(r'\b(?:open|launch|start|run)\s+' + re.escape(key) + r'\b', text):
                return key
        elif re.search(r'\b' + re.escape(key) + r'\b', text):
            return key
    return None


def _find_monitor_in_text(text):
    text = text.lower()
    for alias in sorted(MONITOR_ALIASES, key=len, reverse=True):
        if alias in text:
            return MONITOR_ALIASES[alias]
    return None


_SYSTEM_RESPONSES = {
    "shutdown": "Initiating shutdown sequence. You have 5 seconds to cancel, sir.",
    "restart": "Restarting the system now, sir.",
    "sleep": "Putting the system into sleep mode, sir.",
    "lock": "Locking the workstation, sir.",
    "cancel_shutdown": "Shutdown sequence aborted, sir.",
    "mute": "Audio muted, sir.",
    "minimize_all": "Clearing the workspace, sir.",
    "screenshot": "Capturing the screen now, sir.",
}


def _describe_actions_regex(actions):
    if not actions:
        return "I'm sorry sir, I didn't quite catch that."

    parts = []
    for a in actions:
        t = a["type"]
        if t == "open_app":
            name = a["app"].title()
            if a.get("monitor") is not None:
                mon = _INDEX_NAME.get(a["monitor"], f"monitor {a['monitor']}")
                parts.append(f"launching {name} on the {mon} display")
            else:
                parts.append(f"launching {name}")
        elif t == "close_app":
            parts.append(f"closing {a['app'].title()}")
        elif t == "volume":
            parts.append(f"adjusting volume to {a['level']} percent")
        elif t in _SYSTEM_RESPONSES:
            return _SYSTEM_RESPONSES[t]

    if len(parts) == 1:
        return f"Right away, sir. {parts[0].capitalize()}."
    return "Very well, sir. " + ", ".join(parts[:-1]) + " and " + parts[-1] + "."
