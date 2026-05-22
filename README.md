# Winter

A local-first AI desktop assistant for **macOS and Windows**. Voice commands,
camera hand gestures, and switchable character personalities — running fully
offline (only web-search questions touch the internet).

- **Voice** — custom wake word (Vosk) → speech-to-text (`faster-whisper`) →
  intent → action;
  the system volume dips briefly while it captures your command. Optional macOS
  echo cancellation (`audio.echo_cancellation` in settings) cancels playing
  audio from the mic, at the cost of dimming other audio while it runs.
- **Brain** — local LLM via Ollama
- **Voice replies** — local neural TTS with character voice cloning
- **Camera** — MediaPipe hand tracking: swipe gestures + fingertip cursor
- **Characters** — create your own (name, personality, sprite, cloned voice) and switch between them
- **Visualizer** — a transparent, always-on-top audio-reactive widget

All five build phases are complete: voice commands, personality + voice +
web Q&A, the on-screen sprite, camera gestures, and polish + packaging.
For contributor/architecture notes see `CLAUDE.md`.

## Quick install

One command installs everything — uv, Ollama, Winter, and the AI model — into
a `Winter` folder in your home directory.

**macOS / Linux** — paste into Terminal:

```sh
curl -fsSL https://raw.githubusercontent.com/awinterblue/winter/main/scripts/bootstrap.sh | bash
```

**Windows** — paste into PowerShell:

```powershell
irm https://raw.githubusercontent.com/awinterblue/winter/main/scripts/bootstrap.ps1 | iex
```

On Windows, if a prerequisite is missing the command installs it and asks you to
run it once more — that second run finishes the job.

## Install step by step

Prefer to do it by hand? First install the two prerequisites —
**[uv](https://docs.astral.sh/uv/)** (`brew install uv`) and
**[Ollama](https://ollama.com)**. Then:

```sh
git clone https://github.com/awinterblue/winter.git
cd winter
./scripts/install.sh          # Windows:  scripts\install.ps1
ollama pull llama3.2:3b
```

`install.sh` creates the Python 3.12 environment and installs everything (a few
GB, one time). For the full Windows walkthrough see `SETUP_WINDOWS.md`.

Every character uses the fast built-in Piper voice. To enable voice **cloning**
(so a character can clone a voice from an uploaded clip), set up its isolated
environment once — no compiler needed, on any platform:

```sh
.venv/bin/python scripts/setup_voice.py
```

To update later: `./scripts/update.sh` (Windows: `scripts\update.ps1`).

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

The easy way: tray menu → **Create Character…** — give it a name, a personality,
and optionally a sprite image and a voice clip (audio or video). Winter builds
the character and switches to it. Remove characters from the Settings window.

Under the hood each character is a folder in `config/characters/<id>/` with a
`character.yaml` (name, wake word, personality, TTS settings). Characters you
create stay **local to your machine** — only the built-in "Winter" character
ships with the repo. `tts.engine` picks the voice: `piper` (fast, generic) or
`chatterbox` (clones a `reference.wav`; needs `scripts/setup_voice.py`).
