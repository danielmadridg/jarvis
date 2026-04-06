"""
Test mode — type or speak commands without needing wake word.
Usage:
  python test.py          -> keyboard mode (type commands)
  python test.py --voice  -> voice mode (speak directly)
  python test.py --stt    -> STT debug (just shows what it hears)
"""
import sys
import threading

sys.path.insert(0, ".")

from speech import listen_and_transcribe, speak
from command_parser import parse_command
from window_manager import (
    open_app, move_to_monitor, close_app, print_monitors,
    shutdown_pc, restart_pc, sleep_pc, lock_pc, cancel_shutdown,
    set_volume, mute_volume, minimize_all, take_screenshot,
)
from config import APPS

_SYSTEM_DISPATCH = {
    "shutdown": shutdown_pc, "restart": restart_pc, "sleep": sleep_pc,
    "lock": lock_pc, "cancel_shutdown": cancel_shutdown, "mute": mute_volume,
    "minimize_all": minimize_all, "screenshot": take_screenshot,
}


def execute(action):
    t = action["type"]
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
    elif t in _SYSTEM_DISPATCH:
        _SYSTEM_DISPATCH[t]()


def test_keyboard():
    print_monitors()
    print("  Known apps:", ", ".join(sorted(APPS.keys())[:20]), "...")
    print("\n  Type a command (or 'quit'):")
    while True:
        text = input("\n  > ").strip()
        if text.lower() in ("quit", "exit", "q"):
            break
        actions, response = parse_command(text)
        print(f"  Actions: {actions}")
        print(f"  Response: {response}")
        confirm = input("  Execute? (y/n): ").strip().lower()
        if confirm == "y":
            speak(response)
            for a in actions:
                execute(a)


def test_voice():
    print_monitors()
    print("  Voice mode — speak a command (Ctrl+C to stop)\n")
    while True:
        print("  Listening...")
        text = listen_and_transcribe()
        if not text:
            continue
        print(f"  Heard: \"{text}\"")
        actions, response = parse_command(text)
        print(f"  Actions: {actions}")
        speak(response)
        for a in actions:
            execute(a)


def test_stt():
    print("  STT debug — speak and see transcription (Ctrl+C to stop)\n")
    while True:
        print("  Listening...")
        text = listen_and_transcribe()
        if text:
            print(f"  >>> \"{text}\"\n")
        else:
            print("  (nothing detected)\n")


if __name__ == "__main__":
    if "--voice" in sys.argv:
        test_voice()
    elif "--stt" in sys.argv:
        test_stt()
    else:
        test_keyboard()
