"""Set up Winter's isolated voice-cloning environment.

Voice cloning (the Chatterbox engine) runs in its own virtual environment so
its dependencies never collide with the main app's. This script creates
.venv-voice next to the main .venv, installs Chatterbox into it, and
pre-downloads the voice model.

Run it with Python 3.12:
    macOS/Linux:  .venv/bin/python scripts/setup_voice.py
    Windows:      .venv\\Scripts\\python scripts\\setup_voice.py

It downloads a few GB and takes several minutes. Once it finishes, restart
Winter — characters that have a voice clip will speak in the cloned voice.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICE_VENV = ROOT / ".venv-voice"
# Chatterbox 0.1.7 depends on spacy-pkuseg, which ships prebuilt wheels for
# every platform — so this installs with no C compiler, even on Windows.
PACKAGES = ["chatterbox-tts==0.1.7", "setuptools<81"]


def main() -> int:
    if sys.version_info[:2] != (3, 12):
        print(f"Please run this with Python 3.12 — found "
              f"{sys.version.split()[0]}.")
        return 1

    venv_python = VOICE_VENV / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )

    if not venv_python.exists():
        print(f"Creating the voice environment at {VOICE_VENV} …")
        subprocess.run([sys.executable, "-m", "venv", str(VOICE_VENV)],
                       check=True)

    print("Installing Chatterbox (downloads a few GB — please wait) …")
    subprocess.run([str(venv_python), "-m", "pip", "install", "--quiet",
                    "--upgrade", "pip"], check=True)
    subprocess.run([str(venv_python), "-m", "pip", "install", *PACKAGES],
                   check=True)

    print("Pre-downloading the voice model …")
    subprocess.run(
        [str(venv_python), "-c",
         # fall back to Perth's no-op watermarker if its neural one did not
         # import (it can fail on Windows) — mirrors _chatterbox_worker.py
         "import perth; perth.PerthImplicitWatermarker = ("
         "perth.PerthImplicitWatermarker or perth.DummyWatermarker); "
         "from chatterbox.tts import ChatterboxTTS; "
         "ChatterboxTTS.from_pretrained('cpu')"],
        check=True,
    )

    print("\nVoice cloning is ready. Restart Winter to use it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
