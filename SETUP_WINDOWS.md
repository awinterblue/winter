# Running Winter on Windows

Setup for testing the Windows port on a Windows 10/11 (64-bit) PC.

> ⚠️ The Windows port is **untested on real hardware**. Expect bugs — note any
> errors and report them back so they can be fixed.

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
git checkout windows-port
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

Once it works, you don't need PowerShell — just **double-click `winter.bat`**
in the project folder. It starts Winter with no console window (the assistant
appears in the system tray). Right-click `winter.bat` → *Create shortcut* and
drag the shortcut to your Desktop or pin it to the taskbar for one-click access.

While you're still **debugging the Windows port**, keep launching with
`python -m winter` in PowerShell — that shows the error output. `winter.bat`
hides the console, so you wouldn't see errors.

## Notes

- **Models** (speech, hand-tracking) download themselves on first run; the
  voice and LLM models download on first use.
- **No special permissions** are needed on Windows for the volume/media/cursor
  control — unlike macOS.
- The **camera** and **microphone** may prompt Windows' privacy dialog the
  first time — allow them.
- **Echo cancellation** is macOS-only; Windows uses the plain microphone.
- To pull fixes later: `git pull` in the `winter` folder.
