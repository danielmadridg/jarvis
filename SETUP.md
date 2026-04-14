# Jarvis Setup Guide

## Environment Variables

Jarvis requires API keys to be set via environment variables. **Never commit actual keys to the repository.**

### 1. Create a `.env` file

Copy `.env.example` to create your `.env` file:

```bash
cp .env.example .env
```

### 2. Fill in your credentials

Edit `.env` and add your actual API keys:

```
ANTHROPIC_API_KEY=sk-ant-v0-...your-actual-key...
OPENAI_API_KEY=sk-...your-actual-key...
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SHORTCUTS_DIR=C:\ALL\Shortcuts
```

### How to Get Your API Keys

#### Anthropic API Key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Navigate to "API Keys"
4. Create a new API key
5. Copy it and add to `.env`

#### OpenAI API Key (Optional - fallback)
1. Go to [platform.openai.com](https://platform.openai.com)
2. Create an account
3. Go to API keys section
4. Generate a new secret key
5. Add to `.env`

#### Spotify Credentials
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create an app
3. Accept the terms
4. Copy your Client ID
5. Click "Show Client Secret" and copy it
6. Add both to `.env`
7. **Important:** Jarvis uses the [Authorization Code Flow](https://developer.spotify.com/documentation/web-api/tutorials/code-flow), which will open a browser for first-time auth

### 3. Test Your Setup

Run Jarvis and it will automatically use the variables from `.env`:

```bash
python main.py
```

## Spotify First-Run Authorization

On first use, Jarvis will:
1. Open your browser to Spotify's auth page
2. Ask for permission
3. Redirect to `http://127.0.0.1:8888/callback`
4. Save your auth token locally (in `.spotify_cache`)

The `.spotify_cache` is ignored by `.gitignore` and never committed.

## Security Notes

- ✅ `.env` is in `.gitignore` — it will never be committed
- ✅ API keys only loaded at runtime from environment
- ✅ No keys are logged or printed
- ✅ Spotify tokens are stored locally, not in code
- ✅ Always keep your `.env` file private and never share it

## Troubleshooting

### "No ANTHROPIC_API_KEY found"
- Make sure you created a `.env` file with `ANTHROPIC_API_KEY=...`
- Verify the file is in the root Jarvis directory (same location as `main.py`)

### Spotify Auth Fails
- Check that `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` are correct
- Verify they're in your `.env` file
- If the redirect URI changes, update it in `config.py`: `SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"`

### "Still listening..." message keeps appearing
- Increase `ENERGY_THRESHOLD` in `speech.py` if background noise is high
- Run `python wake_word.py` separately to test wake word detection
- Check that your microphone is working: `python -c "import pyaudio; print(pyaudio.PyAudio().get_device_count())"`

## On Different Machines

When cloning Jarvis on a new machine:
1. Clone the repo: `git clone ...`
2. Install dependencies: `pip install -r requirements.txt`
3. Create `.env` file with your API keys (copy from `.env.example`)
4. Run: `python main.py`

The `.env` file is **local only** — each machine needs its own.

## Environment Variable Precedence

Jarvis checks for credentials in this order:
1. Environment variable (highest priority)
2. `.env` file in current directory
3. Empty string (uses fallback behavior)

This means you can also set environment variables globally instead of using `.env`:

### Windows PowerShell
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:SPOTIFY_CLIENT_ID="your-id"
$env:SPOTIFY_CLIENT_SECRET="your-secret"
python main.py
```

### Windows CMD
```cmd
set ANTHROPIC_API_KEY=sk-ant-...
set SPOTIFY_CLIENT_ID=your-id
set SPOTIFY_CLIENT_SECRET=your-secret
python main.py
```

### Mac/Linux
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export SPOTIFY_CLIENT_ID="your-id"
export SPOTIFY_CLIENT_SECRET="your-secret"
python main.py
```

## Never Do This ❌

```python
# ❌ DON'T hardcode keys
ANTHROPIC_API_KEY = "sk-ant-..."

# ❌ DON'T commit .env files
git add .env

# ❌ DON'T share your .env file
cat .env | pbcopy  # macOS
```

## Always Do This ✅

```python
# ✅ DO use environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ✅ DO use .env.example as a template
cp .env.example .env

# ✅ DO keep .env private
# It's already in .gitignore
```

---

**Questions?** Check the [README.md](README.md) for more details about Jarvis features.
