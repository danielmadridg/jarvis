# Jarvis — Voice-Controlled AI Assistant for Windows

A sophisticated voice-activated AI butler inspired by Iron Man's Jarvis, bringing natural language understanding and intelligent automation to your Windows desktop.

## Features

### 🎤 Voice Control
- **Wake word detection** with "Jarvis" trigger
- **Real-time transcription** using Whisper (faster-whisper) on GPU
- **Natural language understanding** via Claude Haiku API
- **Text-to-speech responses** with Edge TTS
- **Streaming detection** — execute actions while you're still talking
- **Interrupt detection** — say something to interrupt Jarvis mid-speech

### 🚀 App Management
- **Open/close applications** by voice
- **Multi-monitor support** — move apps to specific monitors
- **Quick shortcuts** — auto-scans your shortcuts folder for app recognition

### 🎵 Spotify Integration
- **Play songs, playlists, or artists** by voice search
- **Playback control** — pause, resume, next, previous
- **Smart search** — checks your library first, then public playlists

### ⏱️ Timers & Reminders
- **Set timers** with custom labels
- **Set reminders** with voice-triggered messages
- **Cancel timers** on demand

### 🌐 Web & Search
- **Open URLs** directly ("open github.com")
- **Google Search** voice queries
- **YouTube Search** with one command

### 🎮 Gaming Mode
- **Auto-close distracting apps** when gaming starts
- **Restore** apps when gaming ends

### 🔧 System Control
- **Shutdown, restart, sleep, lock PC**
- **Volume control** (0-100%)
- **Brightness adjustment**
- **Screenshots** and clipboard management
- **Run PowerShell/CMD commands** directly

### 📁 File Operations
- **Read/write files** by voice
- **Find files** with search queries
- **File content** accessible through voice

### 🖥️ Advanced Controls
- **Screen reading** with OCR (Claude vision)
- **Mouse movement & clicks**
- **Keyboard input** automation
- **System information** retrieval
- **Clipboard** read/write operations

### 🧠 Memory System
- **Remember facts** — persistent key-value storage
- **Recall information** — retrieve saved data anytime
- **Forget entries** — remove specific memories

### 📰 Additional Features
- **Daily morning greeting** on first launch
- **Weather information** (auto-location)
- **Current time & date** awareness
- **Self-healing** — retries with alternative approaches on failure
- **Easter eggs** — hidden voice responses

## Requirements

### Hardware
- **GPU** (NVIDIA RTX recommended) — for Whisper fast inference (~0.2s per transcription)
- **Microphone** for voice input
- **Speaker** for audio output

### Software
```
Python 3.10+
```

### API Keys (in `.env`)
```
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here (optional, for fallback)
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_secret
SHORTCUTS_DIR=C:\ALL\Shortcuts (or your shortcuts folder)
```

## Installation

### 1. Clone the repository
```bash
git clone <repo-url>
cd Jarvis
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up environment variables
Create a `.env` file in the project root:
```
ANTHROPIC_API_KEY=sk-ant-...
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_secret
SHORTCUTS_DIR=C:\ALL\Shortcuts
```

### 4. Configure Spotify (optional)
1. Create an app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Get your Client ID and Secret
3. Add to `.env`

### 5. Set up shortcuts folder
Create a folder with `.lnk` / `.url` / `.exe` shortcuts for your apps. Jarvis will auto-discover them.

### 6. Run Jarvis
```bash
python main.py
```

## Usage

### Wake & Listen
```
You: "Jarvis"
Jarvis: [Beep] Ready to listen...
```

### Voice Commands Examples

**Apps & Windows:**
- "Open Spotify"
- "Close Discord"
- "Take a screenshot"
- "Move VS Code to the right monitor"

**Media:**
- "Play some lo-fi beats"
- "Play my gym playlist"
- "Next track / Previous track"

**Timers:**
- "Set a 5 minute timer for laundry"
- "Remind me to check the oven in 20 minutes"

**Search:**
- "Google how to make pasta"
- "Search YouTube for guitar tutorials"
- "Open amazon.com"

**System:**
- "Shut down the PC"
- "What's the weather?"
- "What time is it?"
- "Set brightness to 80"

**Gaming:**
- "Gaming mode on" (closes distracting apps)
- "Gaming mode off" (restores them)

**Memory:**
- "Remember my password is 123ABC"
- "What's my password?"
- "Forget my password"

## Configuration

Edit `config.py` to customize:

```python
# Wake word
WAKE_WORD = "jarvis"

# AI Model size (base recommended for GPU)
WHISPER_MODEL = "base"

# TTS Voice (supports many languages/accents)
EDGE_TTS_VOICE = "en-GB-RyanNeural"

# Monitor layout (adjust to your setup)
MONITOR_ALIASES = {
    "arriba": 0,      # Top monitor
    "centro": 1,      # Center/main monitor
    "izquierda": 2,   # Left monitor
    "derecha": 3,     # Right monitor
}

# Shortcuts folder for app discovery
SHORTCUTS_DIR = r"C:\ALL\Shortcuts"
```

## Architecture

- **main.py** — Core conversation loop, action execution
- **speech.py** — STT (Whisper), TTS (Edge), audio streaming
- **command_parser.py** — Natural language parsing (Claude), regex fallback
- **window_manager.py** — Windows API integration for app control
- **spotify_player.py** — Spotify API integration
- **utilities.py** — Timers, reminders, file ops, system control
- **wake_word.py** — Wake word detection (openwakeword)
- **config.py** — Configuration & app shortcuts discovery

## Performance Notes

- **STT latency:** ~0.2s per transcription (on RTX 5080)
- **Streaming detection:** Actions execute while user is still talking
- **TTS caching:** Pre-caches common phrases for ~0 latency
- **CUDA optimization:** Configured for float16 inference

## Troubleshooting

### Jarvis doesn't respond to wake word
- Check microphone levels
- Verify `sounddevice` can access your mic
- Try `python wake_word.py` directly

### Whisper takes too long
- Ensure CUDA is properly installed
- Check `nvidia-smi` to verify GPU usage
- Fall back to CPU: change `device="cuda"` to `device="cpu"` in speech.py

### Spotify commands fail
- Verify Spotify API credentials in `.env`
- Check Spotify premium status (required for API playback)
- Restart Spotify app

### TTS voice distorted
- Adjust `EDGE_TTS_PITCH` and `EDGE_TTS_RATE` in config.py
- Try a different voice from the `en-*` options

## Future Enhancements

- [ ] Multi-language support
- [ ] Custom wake words
- [ ] Home automation integration (smart lights, etc.)
- [ ] Email client integration
- [ ] Calendar/scheduling features
- [ ] Browser automation
- [ ] Advanced context memory with embeddings

## License

MIT License — Feel free to fork and customize!

## Credits

Built with:
- [Claude AI](https://claude.ai) — Natural language understanding
- [Whisper](https://openai.com/research/whisper) — Speech-to-text
- [Edge TTS](https://github.com/rany2/edge-tts) — Text-to-speech
- [Spotify API](https://developer.spotify.com) — Music streaming
- [OpenWakeword](https://github.com/dscripka/openWakeWord) — Wake word detection

---

**Enjoy your AI butler!** 🎩
