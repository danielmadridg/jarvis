"""
Clap detection debugger — uses the same ClapDetector as wake_word.py.
Clap twice to test. Press Ctrl+C to stop.
"""
import numpy as np
import sounddevice as sd
import time
import sys
sys.path.insert(0, r"c:\ALL\Coding\jarvis")
from wake_word import ClapDetector

SAMPLE_RATE = 16000
detector = ClapDetector(SAMPLE_RATE)

print("=" * 52)
print("  Clap Detection Debugger")
print("=" * 52)
print()
print("  Clap twice and watch. Ctrl+C to stop.")
print()

def callback(indata, frames, time_info, status):
    chunk = indata[:, 0]
    rms = float(np.sqrt(np.mean(chunk ** 2)))
    peak = float(np.max(np.abs(chunk)))
    now = time.time()

    if peak > 0.02:
        ratio = rms / detector._ambient_rms if detector._ambient_rms > 0 else 0
        bar = "#" * int(min(peak, 1.0) * 80)
        marker = ""
        if ratio > detector._spike_ratio and peak > detector._min_peak:
            marker = " <<< CLAP!"
        print(f"  peak={peak:.4f} rms={rms:.4f} ambient={detector._ambient_rms:.4f} ratio={ratio:.1f}x {bar}{marker}")

    if detector.feed(chunk, now):
        print()
        print("  *** DOUBLE CLAP DETECTED! ***")
        print()

try:
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=2000, callback=callback):
        print(f"  spike_ratio={detector._spike_ratio}x  min_peak={detector._min_peak}")
        print(f"  Listening...\n")
        while True:
            time.sleep(0.1)
except KeyboardInterrupt:
    print("\n  Done.")
