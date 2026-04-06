"""
Jarvis — Voice-controlled Windows assistant
"""
# Add CUDA DLL paths before any imports that need them
import os as _os
_nvidia_path = _os.path.join(
    _os.path.expanduser("~"),
    "AppData", "Local", "Packages",
    "PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0",
    "LocalCache", "local-packages", "Python313", "site-packages", "nvidia",
)
for _subdir in ("cublas", "cuda_runtime", "cudnn"):
    _bin = _os.path.join(_nvidia_path, _subdir, "bin")
    if _os.path.isdir(_bin):
        _os.add_dll_directory(_bin)
        _os.environ["PATH"] = _bin + ";" + _os.environ.get("PATH", "")

import threading
import numpy as np
import sounddevice as sd

from config import SAMPLE_RATE, JARVIS_NAME
from speech import listen_and_transcribe, listen_streaming, speak, preload
from command_parser import parse_command, detect_actions_fast, clear_conversation
from window_manager import (
    open_app, move_to_monitor, close_app, print_monitors,
    shutdown_pc, restart_pc, sleep_pc, lock_pc, cancel_shutdown,
    set_volume, mute_volume, minimize_all, take_screenshot,
)
from spotify_player import (
    play_search, pause as spotify_pause, resume as spotify_resume,
    next_track, previous_track,
)
from utilities import (
    set_timer, set_reminder, cancel_timer,
    open_url, search_google, search_youtube,
    set_brightness, get_news,
    remember, recall, forget,
    gaming_mode_on, gaming_mode_off,
    is_new_day, generate_morning_greeting,
    run_command, run_powershell, read_file, write_file, find_files,
    read_screen, type_text, press_key, mouse_click,
    get_system_info, get_clipboard, set_clipboard,
)

_busy = threading.Lock()


def _beep(freq=880, duration=0.12):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), dtype=np.float32)
    tone = (np.sin(2 * np.pi * freq * t) * 0.4).astype(np.float32)
    sd.play(tone, samplerate=SAMPLE_RATE)
    sd.wait()


def _is_dismiss(text):
    t = text.lower().strip()
    clean = t.rstrip(".!?,").strip()

    dismiss_exact = {
        "no", "nah", "nope", "nothing", "i'm good", "all good",
        "we're good", "never mind", "go away", "bye", "goodbye",
        "thanks", "thank you", "yes thanks", "yes thank you",
        "that will be all", "that's all", "that's it",
        "stop", "stop listening", "please stop", "shut up",
    }
    if clean in dismiss_exact:
        return True

    dismiss_contains = [
        "that's all", "that's it", "that will be all", "i'm good",
        "no thanks", "no thank", "thank you", "thanks jarvis",
        "goodbye", "bye bye", "see you", "adios", "gracias",
        "stop listening", "please stop", "shut up", "leave me alone",
        "go to sleep", "stand down", "dismissed",
    ]
    return any(p in t for p in dismiss_contains)


def _response_asks_question(response):
    return response.rstrip().endswith("?")


def on_wake(method="voice"):
    if not _busy.acquire(blocking=False):
        return
    try:
        _conversation_loop(method)
    finally:
        _busy.release()


def _conversation_loop(wake_method="voice"):
    clear_conversation()  # fresh context each wake
    if wake_method == "clap":
        print(f"\n  [{JARVIS_NAME}] Woken by double-clap — Listening...")
    else:
        print(f"\n  [{JARVIS_NAME}] Woken by voice — Listening...")
    _beep()

    # Streaming listen: execute actions as detected via regex while still recording
    executed_action_keys = set()

    def _on_new_text(text_so_far):
        """Called with full transcription so far while user is still talking."""
        actions = detect_actions_fast(text_so_far)
        for action in actions:
            key = repr(action)
            if key not in executed_action_keys:
                executed_action_keys.add(key)
                print(f"  [{JARVIS_NAME}] Executing: {action.get('type', '?')} -> {action.get('app', '')}")
                threading.Thread(target=_execute, args=(action,), daemon=True).start()

    text = listen_streaming(_on_new_text)
    if not text:
        text = _listen_with_retries(2)
    if not text:
        speak("I'm here whenever you need me, sir.")
        return

    while True:
        print(f"  [{JARVIS_NAME}] Heard: \"{text}\"")

        if _is_dismiss(text):
            speak("Very well, sir. I'll be here if you need me.")
            return

        # Easter eggs
        if "is this tuff" in text.lower() or "is this tough" in text.lower():
            speak("Hell Yeah, sir.")
            return

        # Final parse with Claude for the spoken response
        actions, response = parse_command(text)

        # Execute any actions that weren't already executed during streaming
        for action in actions:
            key = repr(action)
            if key not in executed_action_keys:
                executed_action_keys.add(key)
                _execute(action)

        # Now speak (user has finished talking, actions already done)
        interrupted = speak(response)

        if interrupted:
            import time as _time
            _time.sleep(0.3)
            print(f"  [{JARVIS_NAME}] Listening after interrupt...")
            text = _keep_listening()
            if not text:
                continue
            continue

        if _response_asks_question(response):
            print(f"  [{JARVIS_NAME}] Waiting for response...")
            executed_action_keys.clear()
            text = _keep_listening()
            if not text:
                continue
            continue

        if actions:
            interrupted = speak("Anything else, sir?")
            if interrupted:
                import time as _time
                _time.sleep(0.3)
                print(f"  [{JARVIS_NAME}] Listening after interrupt...")
                executed_action_keys.clear()
                text = _keep_listening()
                if not text:
                    continue
                continue

        # No actions and no question — still keep listening
        executed_action_keys.clear()
        text = _keep_listening()
        if not text:
            continue
        continue


def _listen_with_retries(max_retries):
    for i in range(max_retries):
        text = listen_and_transcribe()
        if text:
            return text
        if i < max_retries - 1:
            print(f"  [{JARVIS_NAME}] Still listening...")
    return ""


def _keep_listening():
    """Keep listening indefinitely until user says something."""
    while True:
        text = listen_and_transcribe()
        if text:
            return text


_SYSTEM_DISPATCH = {
    "shutdown": shutdown_pc,
    "restart": restart_pc,
    "sleep": sleep_pc,
    "lock": lock_pc,
    "cancel_shutdown": cancel_shutdown,
    "mute": mute_volume,
    "minimize_all": minimize_all,
    "screenshot": take_screenshot,
}


def _execute(action):
    try:
        _execute_inner(action)
    except Exception as e:
        error_msg = str(e)
        print(f"  [{JARVIS_NAME}] Action failed: {error_msg}")
        # Self-healing: ask Claude to suggest a fix
        try:
            from command_parser import parse_command as _reparse
            retry_text = f"The command '{action}' failed with error: {error_msg}. Try an alternative approach."
            new_actions, response = _reparse(retry_text)
            if new_actions:
                print(f"  [{JARVIS_NAME}] Self-healing: retrying with {new_actions[0].get('type', '?')}")
                _execute_inner(new_actions[0])
            else:
                speak(f"I'm afraid that didn't work, sir. {error_msg}")
        except Exception:
            speak(f"I'm afraid that didn't work, sir.")


def _execute_inner(action):
    t = action["type"]

    # App management
    if t == "open_app":
        app = action["app"]
        mon = action.get("monitor")
        open_app(app)
        if mon is not None:
            threading.Thread(target=move_to_monitor, args=(app, mon), daemon=True).start()
    elif t == "close_app":
        close_app(action["app"])
    elif t == "volume":
        set_volume(action["level"])

    # Spotify
    elif t == "play_spotify":
        try: play_search(action["query"])
        except Exception as e: print(f"  [spotify] {e}")
    elif t == "spotify_pause":
        try: spotify_pause()
        except Exception as e: print(f"  [spotify] {e}")
    elif t == "spotify_resume":
        try: spotify_resume()
        except Exception as e: print(f"  [spotify] {e}")
    elif t == "spotify_next":
        try: next_track()
        except Exception as e: print(f"  [spotify] {e}")
    elif t == "spotify_previous":
        try: previous_track()
        except Exception as e: print(f"  [spotify] {e}")

    # Timers & Reminders
    elif t == "set_timer":
        set_timer(action["seconds"], action.get("label", "Timer"))
    elif t == "set_reminder":
        set_reminder(action["seconds"], action["message"])
    elif t == "cancel_timer":
        cancel_timer(action.get("label"))

    # URLs & Search
    elif t == "open_url":
        open_url(action["url"])
    elif t == "search_google":
        search_google(action["query"])
    elif t == "search_youtube":
        search_youtube(action["query"])

    # Brightness
    elif t == "set_brightness":
        set_brightness(action["level"])

    # Memory
    elif t == "remember":
        remember(action["key"], action["value"])
    elif t == "forget":
        forget(action["key"])

    # Gaming
    elif t == "gaming_mode_on":
        closed = gaming_mode_on()
        if closed:
            print(f"  [gaming] Closed: {', '.join(closed)}")
    elif t == "gaming_mode_off":
        gaming_mode_off()

    # Shell commands
    elif t == "run_command":
        output = run_command(action["command"])
        print(f"  [cmd] {output[:200]}")
    elif t == "run_powershell":
        output = run_powershell(action["command"])
        print(f"  [ps] {output[:200]}")

    # File operations
    elif t == "read_file":
        content = read_file(action["path"])
        print(f"  [file] Read {action['path']}: {content[:100]}...")
    elif t == "write_file":
        write_file(action["path"], action["content"])
    elif t == "find_files":
        results = find_files(action["query"], action.get("dir"))
        print(f"  [find] {len(results)} files found")

    # Screen reading
    elif t == "read_screen":
        answer = read_screen(action.get("question", "What's on the screen?"))
        from speech import speak as _speak
        _speak(answer)

    # Keyboard & Mouse
    elif t == "type_text":
        type_text(action["text"])
    elif t == "press_key":
        press_key(action["key"])
    elif t == "mouse_click":
        mouse_click(action.get("x"), action.get("y"), action.get("button", "left"))

    # System info
    elif t == "system_info":
        info = get_system_info()
        print(f"  [sys] {info}")

    # Clipboard
    elif t == "read_clipboard":
        text = get_clipboard()
        from speech import speak as _speak
        _speak(text)
    elif t == "set_clipboard":
        set_clipboard(action["text"])

    # System
    elif t in _SYSTEM_DISPATCH:
        _SYSTEM_DISPATCH[t]()


def main():
    print("=" * 52)
    print(f"  {JARVIS_NAME} — Voice Assistant for Windows")
    print("=" * 52)
    print()

    print_monitors()

    print("  [init] Preloading models...")
    preload()

    # Daily morning greeting on first launch of the day
    if is_new_day():
        print(f"  [{JARVIS_NAME}] New day detected — preparing greeting...")
        greeting = generate_morning_greeting()
        print(f"  [{JARVIS_NAME}] {greeting}")
        speak(greeting)

        # Listen for follow-up after greeting
        text = _listen_with_retries(2)
        if text and not _is_dismiss(text):
            actions, response = parse_command(text)
            speak(response)
            for action in actions:
                _execute(action)

    print(f"  [{JARVIS_NAME}] Ready. Say 'Jarvis' to begin.\n")

    from wake_word import listen_for_wake_word
    listen_for_wake_word(on_wake)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n  [{JARVIS_NAME}] Shutting down. Goodbye, sir.")
