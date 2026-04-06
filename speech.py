"""
Speech services:
  - STT via faster-whisper on GPU (RTX 5080) — ~0.2s per transcription
  - TTS via Edge TTS with interruption support + pre-cached common phrases
  - Ambient noise calibrated once at startup, not every listen call
"""
import asyncio
import tempfile
import os
import threading
import numpy as np
import sounddevice as sd
import speech_recognition as sr
from config import (
    SAMPLE_RATE, EDGE_TTS_VOICE, EDGE_TTS_PITCH, EDGE_TTS_RATE,
    APPS,
)

_recognizer = sr.Recognizer()
_whisper_model = None
_pygame_ready = False
_interrupted = threading.Event()
_ambient_calibrated = False

# Pre-cached TTS audio for common phrases
_tts_cache = {}
_TTS_CACHE_DIR = os.path.join(tempfile.gettempdir(), "jarvis_tts_cache")


# ── Preload at startup ──────────────────────────────────────────────

def preload():
    global _whisper_model, _pygame_ready, _ambient_calibrated

    if _whisper_model is None:
        print("  [stt] Loading Whisper 'base' on GPU...")
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cuda", compute_type="float16")
        print("  [stt] Whisper 'base' on GPU ready.")

    if not _pygame_ready:
        import pygame
        import time as _time
        for attempt in range(30):
            try:
                pygame.mixer.init()
                _pygame_ready = True
                break
            except pygame.error:
                print(f"  [tts] Audio not ready, retrying ({attempt+1}/30)...")
                _time.sleep(1)
        if not _pygame_ready:
            print("  [tts] WARNING: Audio init failed after 30 retries.")

    # Calibrate ambient noise once
    if not _ambient_calibrated:
        try:
            with sr.Microphone(sample_rate=SAMPLE_RATE) as source:
                _recognizer.adjust_for_ambient_noise(source, duration=0.5)
                _recognizer.energy_threshold = max(_recognizer.energy_threshold, 200)
                _recognizer.dynamic_energy_threshold = True
            _ambient_calibrated = True
            print(f"  [stt] Ambient noise calibrated (threshold: {_recognizer.energy_threshold:.0f})")
        except Exception as e:
            print(f"  [stt] Ambient calibration failed: {e}")

    # Pre-cache common TTS phrases in background
    threading.Thread(target=_precache_tts, daemon=True).start()


def _precache_tts():
    """Pre-generate TTS audio for phrases Jarvis says often."""
    os.makedirs(_TTS_CACHE_DIR, exist_ok=True)
    common_phrases = [
        "Anything else, sir?",
        "Very well, sir. I'll be here if you need me.",
        "Right away, sir.",
        "I'm here whenever you need me, sir.",
        "Hell Yeah, sir.",
    ]
    import edge_tts

    async def _gen(text, path):
        communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE, pitch=EDGE_TTS_PITCH, rate=EDGE_TTS_RATE)
        await communicate.save(path)

    for phrase in common_phrases:
        cache_key = phrase.lower().strip()
        cache_path = os.path.join(_TTS_CACHE_DIR, f"{hash(cache_key)}.mp3")
        if not os.path.exists(cache_path):
            try:
                asyncio.run(_gen(phrase, cache_path))
            except Exception:
                continue
        _tts_cache[cache_key] = cache_path
    print(f"  [tts] Pre-cached {len(_tts_cache)} common phrases.")


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cuda", compute_type="float16")
    return _whisper_model


# ── STT via faster-whisper on GPU ──────────────────────────────────

_whisper_prompt = None

def _get_whisper_prompt():
    global _whisper_prompt
    if _whisper_prompt is None:
        app_names = ", ".join(sorted(set(k.title() for k in APPS.keys()))[:50])
        _whisper_prompt = (
            f"Jarvis is a voice assistant. The user says 'Jarvis' or 'Hey Jarvis'. "
            f"The user mixes English and Spanish freely. "
            f"Names: Lana Del Rey, Bad Bunny, Rosalia, Peso Pluma. "
            f"Apps: {app_names}."
        )
    return _whisper_prompt


_JARVIS_CORRECTIONS = {
    "jeremy", "jeremy's", "jervis", "jarva", "jarvus", "jarves",
    "gervis", "javis", "jarvis's", "travis", "jarbus", "jarbi",
    "hervey", "hervis", "jervey",
}


def _fix_transcription(text):
    words = text.split()
    fixed = []
    for w in words:
        if w.lower().rstrip(".,!?'s") in _JARVIS_CORRECTIONS:
            fixed.append("Jarvis")
        else:
            fixed.append(w)
    return " ".join(fixed)


def _transcribe_gpu(audio_np_f32):
    """Transcribe audio using Whisper base on GPU — ~0.2s."""
    model = _get_whisper()
    segments, _ = model.transcribe(
        audio_np_f32, language="en", beam_size=1, best_of=1,
        vad_filter=True,
        initial_prompt=_get_whisper_prompt(),
    )
    text = " ".join(seg.text.strip() for seg in segments)
    return _fix_transcription(text.strip())


def listen_and_transcribe():
    """Record from mic until silence, then transcribe via OpenAI. Returns '' on timeout."""
    with sr.Microphone(sample_rate=SAMPLE_RATE) as source:
        # Skip ambient calibration — already done at startup
        _recognizer.pause_threshold = 1.8
        _recognizer.phrase_threshold = 0.2

        try:
            audio = _recognizer.listen(source, timeout=5, phrase_time_limit=20)
        except sr.WaitTimeoutError:
            return ""

    raw = audio.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2)
    audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return _transcribe_gpu(audio_np)


# ── TTS with interruption support ───────────────────────────────────

def _monitor_mic_for_interrupt():
    _interrupted.clear()
    baseline_samples = []
    calibrated = threading.Event()
    baseline_rms = [0.05]
    consecutive_loud = [0]

    def _cb(indata, frames, time_info, status):
        rms = float(np.sqrt(np.mean(indata ** 2)))

        if not calibrated.is_set():
            baseline_samples.append(rms)
            if len(baseline_samples) >= 25:
                avg = sum(baseline_samples) / len(baseline_samples)
                baseline_rms[0] = max(avg * 2.5, 0.03)
                calibrated.set()
            return

        if rms > baseline_rms[0]:
            consecutive_loud[0] += 1
            if consecutive_loud[0] >= 4:
                _interrupted.set()
        else:
            consecutive_loud[0] = 0

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            blocksize=3200, callback=_cb):
            while not _interrupted.is_set():
                _interrupted.wait(timeout=0.05)
    except Exception:
        pass


def speak(text):
    """Speak text via Edge TTS. Uses cache for common phrases."""
    if not text:
        return
    print(f"  [tts] {text}")
    import pygame

    # Check cache first
    cache_key = text.lower().strip()
    cached_path = _tts_cache.get(cache_key)

    if cached_path and os.path.exists(cached_path):
        tmp = cached_path
    else:
        # Generate on the fly with unique temp file to avoid lock conflicts
        import edge_tts
        fd, tmp = tempfile.mkstemp(suffix=".mp3", prefix="jarvis_tts_")
        os.close(fd)

        async def _gen():
            communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE, pitch=EDGE_TTS_PITCH, rate=EDGE_TTS_RATE)
            with open(tmp, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])

        asyncio.run(_gen())

    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.unload()
        pygame.mixer.music.load(tmp)
        pygame.mixer.music.play()

        _interrupted.clear()
        mic_thread = threading.Thread(target=_monitor_mic_for_interrupt, daemon=True)
        mic_thread.start()

        while pygame.mixer.music.get_busy():
            if _interrupted.is_set():
                pygame.mixer.music.stop()
                print(f"  [tts] Interrupted by user.")
                break
            pygame.time.wait(30)

        pygame.mixer.music.unload()
        # Clean up temp file (but not cached ones)
        if tmp != cached_path:
            try:
                os.remove(tmp)
            except OSError:
                pass
        return _interrupted.is_set()
    except Exception as e:
        print(f"  [tts] Edge TTS error: {e}")
        return False


def listen_streaming(on_new_text):
    """
    Record audio continuously. Every ~1.5s, transcribe the FULL accumulated
    audio and call on_new_text(full_text_so_far) with the latest transcription.
    Stops after 2s of silence. Returns final complete transcription.
    """
    import time as _time
    import queue

    audio_q = queue.Queue()
    audio_chunks = []
    last_speech_time = [_time.time()]
    SILENCE_TIMEOUT = 2.0
    TRANSCRIBE_INTERVAL = 1.5
    MAX_DURATION = 30
    last_text = [""]
    has_speech = [False]

    def _audio_cb(indata, frames, time_info, status):
        audio_q.put(indata[:, 0].copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=3200, callback=_audio_cb):

        last_transcribe_time = _time.time()
        recording_start = _time.time()

        while True:
            # Drain queue
            try:
                chunk = audio_q.get(timeout=0.05)
            except queue.Empty:
                chunk = None

            if chunk is not None:
                audio_chunks.append(chunk)
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                if rms > 0.006:
                    last_speech_time[0] = _time.time()
                    has_speech[0] = True

            now = _time.time()

            # Stop after silence (only if we've heard something)
            if has_speech[0] and (now - last_speech_time[0]) > SILENCE_TIMEOUT:
                break

            # Hard timeout
            if (now - recording_start) > MAX_DURATION:
                break

            # Timeout if no speech at all after 5s
            if not has_speech[0] and (now - recording_start) > 5:
                break

            # Periodic transcription of FULL audio
            if has_speech[0] and (now - last_transcribe_time) >= TRANSCRIBE_INTERVAL and len(audio_chunks) > 0:
                last_transcribe_time = now
                full_audio = np.concatenate(audio_chunks)
                text = _transcribe_gpu(full_audio)
                if text and text != last_text[0]:
                    print(f"  [stream] \"{text}\"")
                    last_text[0] = text
                    on_new_text(text)

    # Final transcription of complete audio
    if audio_chunks:
        full_audio = np.concatenate(audio_chunks)
        final_text = _transcribe_gpu(full_audio)
        return final_text
    return ""


def was_interrupted():
    return _interrupted.is_set()
