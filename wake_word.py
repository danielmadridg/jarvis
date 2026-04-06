"""
Wake-word detection via OpenWakeWord (hey_jarvis model) + double-clap.
Much more reliable than Whisper for wake word detection, especially with
background noise or distance.
"""
import time
import numpy as np
import sounddevice as sd
import queue
from config import SAMPLE_RATE


# ── Double-clap detector ──────────────────────────────────────────

class ClapDetector:
    """Detects two sharp claps by looking for sudden RMS spikes above ambient."""

    def __init__(self, sample_rate=SAMPLE_RATE):
        self.sr = sample_rate
        self.gap_min = 0.15
        self.gap_max = 0.6
        self.last_clap_time = 0
        self.clap_count = 0
        self.cooldown_until = 0
        self._ambient_rms = 0.005
        self._spike_ratio = 4.0
        self._min_peak = 0.06
        self._in_clap = False

    def feed(self, audio_chunk, chunk_time):
        """Feed audio data. Returns True if double-clap detected."""
        if chunk_time < self.cooldown_until:
            return False

        rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
        peak = float(np.max(np.abs(audio_chunk)))

        is_spike = (peak > self._min_peak and
                    rms > self._ambient_rms * self._spike_ratio)

        if is_spike and not self._in_clap:
            self._in_clap = True
            gap = chunk_time - self.last_clap_time
            if self.clap_count == 1 and self.gap_min <= gap <= self.gap_max:
                self.clap_count = 0
                self.last_clap_time = 0
                return True
            else:
                self.clap_count = 1
                self.last_clap_time = chunk_time
        elif not is_spike:
            self._in_clap = False
            self._ambient_rms = self._ambient_rms * 0.95 + rms * 0.05

        if self.clap_count == 1 and (chunk_time - self.last_clap_time) > self.gap_max * 1.5:
            self.clap_count = 0

        return False

    def set_cooldown(self, seconds):
        self.cooldown_until = time.time() + seconds
        self.clap_count = 0


# ── OpenWakeWord listener ─────────────────────────────────────────

def listen_for_wake_word(on_detected):
    from openwakeword.model import Model

    # Load the hey_jarvis model (pre-trained, ONNX)
    oww_model = Model(
        wakeword_models=["hey_jarvis_v0.1"],
        inference_framework="onnx",
    )
    print("  [wake] OpenWakeWord 'hey_jarvis' model loaded.")

    audio_q = queue.Queue()
    clap_detector = ClapDetector()

    CHUNK_SIZE = 1280  # OpenWakeWord expects 80ms chunks at 16kHz
    COOLDOWN_SEC = 5.0
    THRESHOLD = 0.5  # confidence threshold for wake word detection

    cooldown_until = 0.0

    def _cb(indata, frames, time_info, status):
        audio_q.put(indata[:, 0].copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=CHUNK_SIZE, callback=_cb):
        print(f"  [wake] Ready -- say \"Hey Jarvis\" or double-clap")

        while True:
            chunk = audio_q.get()
            now = time.time()

            # Check for double-clap
            if now >= cooldown_until and clap_detector.feed(chunk, now):
                print("  [wake] Double-clap detected!")
                cooldown_until = now + COOLDOWN_SEC
                clap_detector.set_cooldown(COOLDOWN_SEC)

                # Drain queue
                while not audio_q.empty():
                    try:
                        audio_q.get_nowait()
                    except queue.Empty:
                        break

                on_detected("clap")

                # Post-conversation drain + cooldown
                while not audio_q.empty():
                    try:
                        audio_q.get_nowait()
                    except queue.Empty:
                        break
                cooldown_until = time.time() + COOLDOWN_SEC
                clap_detector.set_cooldown(COOLDOWN_SEC)
                oww_model.reset()
                continue

            # Skip wake word check during cooldown
            if now < cooldown_until:
                continue

            # Feed audio to OpenWakeWord (expects int16)
            chunk_int16 = (chunk * 32767).astype(np.int16)
            prediction = oww_model.predict(chunk_int16)

            score = prediction.get("hey_jarvis_v0.1", 0)
            if score > THRESHOLD:
                print(f"  [wake] \"Hey Jarvis\" detected (confidence: {score:.2f})")
                cooldown_until = now + COOLDOWN_SEC
                clap_detector.set_cooldown(COOLDOWN_SEC)

                # Drain queue
                while not audio_q.empty():
                    try:
                        audio_q.get_nowait()
                    except queue.Empty:
                        break

                on_detected("voice")

                # Post-conversation drain + cooldown
                while not audio_q.empty():
                    try:
                        audio_q.get_nowait()
                    except queue.Empty:
                        break
                cooldown_until = time.time() + COOLDOWN_SEC
                clap_detector.set_cooldown(COOLDOWN_SEC)
                oww_model.reset()
