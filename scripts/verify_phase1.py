"""Headless functional check for Phase 1 — run with the project venv.

    .venv/bin/python scripts/verify_phase1.py

Exercises settings, characters, the Ollama brain and faster-whisper STT
without needing a microphone (test audio is synthesized with macOS `say`).
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    print("== settings & characters ==")
    from winter.config.character import CharacterManager
    from winter.config.settings import Settings

    settings = Settings.load()
    chars = CharacterManager()
    ids = [c.id for c in chars.list()]
    print("  active character:", settings.active_character)
    print("  characters found:", ids)
    print("  stt model:", settings.stt.model, "| llm:", settings.llm.model)
    assert "hutao" in ids and "default" in ids, "expected character profiles"

    print("\n== macOS volume (read-only) ==")
    from winter.system import macos_control
    print("  current output volume:", macos_control.get_volume(), "%")

    print("\n== Ollama intent parsing ==")
    from winter.brain.llm import OllamaClient
    llm = OllamaClient(settings.llm.model, settings.llm.host)
    commands = [
        "volume up 3",
        "turn it down a bit",
        "next video",
        "pause the music",
        "what is the tallest mountain in the world",
    ]
    for command in commands:
        started = time.time()
        intent = llm.parse_intent(command)
        print(f"  {command!r:45} -> {intent}  ({time.time() - started:.2f}s)")

    print("\n== speech-to-text (faster-whisper) ==")
    import soundfile as sf
    from winter.audio.stt import STTEngine

    print("  loading Whisper model (first run downloads it)…")
    stt = STTEngine(settings.stt.model, settings.stt.compute_type, settings.stt.language)
    wav = Path("/tmp/winter_stt_test.wav")
    for phrase in ["volume up three", "volume down two", "play", "pause", "next"]:
        subprocess.run(
            ["say", "--data-format=LEI16@16000", "-o", str(wav), phrase],
            check=True,
        )
        audio, _ = sf.read(str(wav), dtype="int16")
        if audio.ndim > 1:
            audio = audio[:, 0].copy()
        started = time.time()
        transcript = stt.transcribe(audio)
        print(f"  said {phrase!r:22} -> {transcript!r}  ({time.time() - started:.2f}s)")

    print("\nALL PHASE 1 CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
