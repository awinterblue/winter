# Winter

A local-first AI desktop assistant for macOS. Voice commands, camera hand
gestures, and switchable character personalities — running fully offline (only
web-search questions touch the internet).

- **Voice** — custom wake word (Vosk) → speech-to-text (`faster-whisper`) →
  intent → action;
  the system volume dips briefly while it captures your command. Optional macOS
  echo cancellation (`audio.echo_cancellation` in settings) cancels playing
  audio from the mic, at the cost of dimming other audio while it runs.
- **Brain** — local LLM via Ollama
- **Voice replies** — local neural TTS with character voice cloning
- **Camera** — MediaPipe hand tracking: swipe gestures + fingertip cursor
- **Characters** — switchable personalities and voices (e.g. Hu Tao)
- **Visualizer** — a transparent, always-on-top audio-reactive widget

All five build phases are complete: voice commands, personality + voice +
web Q&A, the on-screen sprite, camera gestures, and polish + packaging.
For contributor/architecture notes see `CLAUDE.md`.

## Setup

Requires **Python 3.12** (MediaPipe has no 3.13 wheel) and [Ollama](https://ollama.com).

```sh
brew install python@3.12 uv ollama
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
.venv/bin/uv pip install -e .
ollama pull llama3.2:3b
```

## Run

```sh
.venv/bin/python -m winter
```

Or double-click **Winter.app** (build it once with `bash scripts/make_app.sh`).
It's a thin launcher that runs the live source, so editing code and relaunching
picks up changes — no rebuild.

The app lives in the menu bar (system tray). Say the wake word, then a command:

- "volume up 3" / "set volume to 40"
- "next" / "pause" / "previous"
- "what's the date" / a question to look up

A glowing orb (the visualizer) floats on screen — drag it anywhere, it
remembers where. It tints by state (blue idle, green listening, amber
thinking, purple speaking) and pulses with Winter's voice. Toggle it from
the tray menu.

Enable **Camera commands** in the tray for hand gestures:

- **Point** your index finger — the cursor follows your fingertip
- **Pinch** thumb to index tip — a single click
- **Open hand, flick** left/right — previous / next track
- **Flat open palm facing the camera, hold high/low** — scroll up / down
  (for Reels / YouTube Shorts); it keeps scrolling while held, faster the
  further from neutral. The flat-palm requirement keeps casual hand
  movements from scrolling by accident. Wherever you first show the palm
  becomes the neutral height.

## macOS permissions

Grant these (System Settings → Privacy & Security). When run from the terminal
they apply to your terminal app; when run as **Winter.app** they apply to Winter:

- **Microphone** — voice capture
- **Accessibility** — media keys, YouTube shortcuts, cursor control
- **Automation** — lets Winter read the active browser tab's URL so "next video"
  works on YouTube (prompts the first time it controls Safari/Chrome)
- **Camera** — hand gestures

## Characters

Each character is a folder under `config/characters/<id>/`:

- `character.yaml` — display name, wake word, personality prompt, TTS params
- `voicelines/` — drop raw voice clips here (any format: .mov, .mp3, .wav …)
- `reference.wav` — the processed ~10–20 s clip Winter clones the voice from

`tts.engine` in `character.yaml` picks the voice:

- `chatterbox` — clones `reference.wav` (sounds like the character, slower)
- `piper` — a fast, generic voice, near real-time (set `tts.voice`)

Add a folder to add a character; switch the active one from the tray menu.
