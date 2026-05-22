# Running Winter on Windows

Setup for testing the Windows port on a Windows 10/11 (64-bit) PC.

> The Windows port has been tested on a Windows 11 PC — voice, camera, volume
> and media keys all work. It's newer than the macOS build, so if you hit a
> problem, note the error and report it.

## 1. Install the prerequisites

Open **PowerShell** and run:

```powershell
winget install astral-sh.uv      # uv — manages Python + packages
winget install Git.Git           # git — to clone the repo
```

Install **Ollama** separately from <https://ollama.com/download> (it's a normal
installer). After it's installed, in a new PowerShell window:

```powershell
ollama pull llama3.2:3b
```

(`uv` fetches Python 3.12 itself in step 3 — you don't need to install Python
by hand.)

## 2. Get the code

```powershell
git clone https://github.com/awinterblue/winter.git
cd winter
```

## 3. Create the environment and install

```powershell
uv venv --python 3.12            # creates .venv (downloads Python 3.12 if needed)
uv pip install -e .              # installs all dependencies (several GB, one time)
```

This installs everything Winter needs to run. Every character uses the fast
**Piper** voice by default; voice **cloning** is an optional add-on — see
"Voice cloning" below.

## 4. Run it

```powershell
.venv\Scripts\python -m winter
```

The first launch downloads the speech and hand-tracking models automatically
(~50 MB). Winter appears in the **system tray** (notification area).

## Voice cloning (optional)

By default Winter speaks every character in the fast built-in Piper voice. To
let a character clone a voice from an uploaded clip, set up the voice
environment once:

```powershell
.venv\Scripts\python scripts\setup_voice.py
```

This creates a separate `.venv-voice` environment and installs the Chatterbox
voice-cloning engine into it (a few GB — it runs fully isolated, so its
dependencies never clash with the main app, and **no C compiler is needed**).
Restart Winter when it finishes.

## Launching it the easy way

- **`winter.vbs`** — the launcher. Double-click it for a clean, **no-window**
  start; Winter appears in the system tray. The bootstrap installer also puts
  a **Winter** shortcut on your Desktop — to create or recreate it by hand
  (e.g. if OneDrive moved your Desktop), run:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\make-shortcut.ps1
  ```
- **`winter-troubleshoot.bat`** — runs Winter in a **visible console** showing
  live output. Use it if Winter doesn't appear, to see the error — but
  **closing that console window stops Winter**, so it's only for diagnosing.

## Notes

- **Models** (speech, hand-tracking) download themselves on first run; the
  voice and LLM models download on first use.
- **No special permissions** are needed on Windows for the volume/media/cursor
  control — unlike macOS.
- The **camera** and **microphone** may prompt Windows' privacy dialog the
  first time — allow them.
- **Echo cancellation** is macOS-only; Windows uses the plain microphone.
- To pull fixes later: `git pull` in the `winter` folder.
