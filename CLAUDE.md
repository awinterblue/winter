# Winter — project guide

Winter is a local-first AI desktop assistant for macOS: voice commands, camera
hand gestures, an on-screen character sprite, and switchable personalities.
Everything runs offline except web-search answers.

## Running it

```sh
.venv/bin/python -m winter        # from the project root
```

Or double-click **Winter.app** (a thin launcher — see Packaging below).

**Requirements:** Python **3.12** (MediaPipe has no 3.13 wheel — the `.venv` is
3.12), [Ollama](https://ollama.com) running with `llama3.2:3b` pulled. The venv
already has every dependency installed.

Winter lives in the **menu bar** (system tray). It has no main window.

## Testing & verification

```sh
.venv/bin/python -m pytest tests/ -q          # unit tests (must stay green)
.venv/bin/python -m compileall -q winter      # quick syntax check
.venv/bin/python scripts/smoke_gui.py         # app constructs without error
```

`scripts/verify_*.py` are functional checks (some need a mic/camera). Run the
relevant one after changing a subsystem.

## Architecture

`AppController` (`winter/app.py`) owns every service and routes all signals.
Cross-thread communication goes through one `EventBus` (`winter/core/events.py`)
of Qt signals — nothing else talks across threads directly.

**Threads** (the Qt UI thread must never block):
- main — widgets, tray, sprite
- `AudioCaptureThread` — mic + wake word + command recording
- `CameraThread` — webcam + MediaPipe hand tracking
- `TTSThread` — owns the torch/MPS voice model (must stay on one thread)
- `QThreadPool` workers (`core/worker.py`) — STT and LLM calls

**Module map:**
- `config/` — `settings.py` (settings.yaml), `character.py` (character folders)
- `core/` — `events.py` (EventBus), `state.py` (AppState/Phase), `worker.py`
- `audio/` — `capture.py`, `micsource.py`, `wakeword.py` (Vosk), `stt.py`
  (faster-whisper), `tts.py` + `tts_thread.py` (Chatterbox / Piper), `sounds.py`
- `brain/` — `llm.py` (Ollama), `router.py` (intent routing), `intents.py`,
  `localfacts.py` (date/time), `websearch.py` (DuckDuckGo)
- `system/` — `macos_control.py` (volume/media keys), `cursor.py`, `permissions.py`
- `vision/` — `camera.py`, `gestures.py`, `cursor_map.py` (One-Euro filter)
- `ui/` — `tray.py`, `visualizer.py` (the sprite), `settings_window.py`

Swappable engines sit behind interfaces: `WakeWordEngine`, `TTSEngine`,
`MicSource`, `WebSearchProvider`.

## How to extend

- **New voice command (exact phrase)** — add to `_FASTPATH` in
  `brain/router.py`. Instant, no LLM.
- **New voice command (flexible)** — add an `IntentType` in `brain/intents.py`,
  mention it in the prompt in `brain/llm.py`, handle it in `router.execute()`.
- **New gesture** — emit a new event name from `GestureEngine`
  (`vision/gestures.py`), handle it in `AppController._on_gesture`.
- **New character** — add a folder under `config/characters/<id>/` with a
  `character.yaml`; optionally `reference.wav` (voice clone) and `sprite/*.png`.
  No code needed.

## Conventions

- Anything blocking runs off the UI thread and reports back via an EventBus
  signal. Never call a model directly from a slot on the main thread.
- macOS permissions needed: Microphone, Accessibility (media keys + cursor),
  Camera, Automation (browser URL for YouTube). See `system/permissions.py`.
- The wake word is a Vosk phrase per character (`wake_word` in character.yaml) —
  use ordinary English words so the recognizer knows them.

## Packaging

`Winter.app` is a thin **alias-style** bundle: its launcher runs the live source
via the `.venv`. Editing code and relaunching the app picks up changes — no
rebuild. Recreate the bundle with `scripts/make_app.sh` (e.g. if the project
moves). It is not portable to other Macs (paths are absolute by design).
