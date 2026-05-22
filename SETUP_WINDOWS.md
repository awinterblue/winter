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

This installs everything Winter needs on Windows. It uses the fast **Piper**
voice. (Chatterbox voice-cloning is an optional extra — `.[voice-cloning]` —
that needs a C compiler to build, so it's left out of the default Windows
install. Winter just uses Piper for every character without it.)

## 4. Run it

```powershell
.venv\Scripts\python -m winter
```

The first launch downloads the speech and hand-tracking models automatically
(~50 MB). Winter appears in the **system tray** (notification area).

## Launching it the easy way

Two launchers sit in the project folder:

- **`winter.vbs`** — double-click for a clean, **no-window** start (the
  assistant just appears in the system tray). Output goes to `winter.log`, so
  if Winter doesn't appear, open that file to see the error. Right-click
  `winter.vbs` → *Create shortcut* and drag it to your Desktop or pin it for
  one-click access.
- **`winter.bat`** — double-click to run with a **visible console** that shows
  live output — handy for troubleshooting.

## Notes

- **Models** (speech, hand-tracking) download themselves on first run; the
  voice and LLM models download on first use.
- **No special permissions** are needed on Windows for the volume/media/cursor
  control — unlike macOS.
- The **camera** and **microphone** may prompt Windows' privacy dialog the
  first time — allow them.
- **Echo cancellation** is macOS-only; Windows uses the plain microphone.
- To pull fixes later: `git pull` in the `winter` folder.
