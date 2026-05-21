"""Verify the dedicated TTS thread and per-character engine routing.

    .venv/bin/python scripts/verify_tts_thread.py

Builds both engines on the dedicated thread, then speaks one line as the
default character (Piper, fast) and one as Hu Tao (Chatterbox, cloned). If both
complete cleanly, the segfault fix and per-character routing both hold.
(You'll hear two short test lines played aloud.)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


def main() -> int:
    app = QApplication(sys.argv)

    from winter.audio.tts_thread import TTSThread
    from winter.config.character import CharacterManager
    from winter.core.events import EventBus

    bus = EventBus()
    manager = CharacterManager()
    state = {"finished": 0}

    def ref(character):
        return character.voice_reference if character.has_voice_reference else None

    def on_ready(ok: bool) -> None:
        print(f"tts engines ready: {ok}")
        if not ok:
            app.quit()
            return
        default = manager.get("default")
        hutao = manager.get("hutao")
        print(f"  default -> {default.tts.get('engine')},  "
              f"hutao -> {hutao.tts.get('engine')}")
        tts.speak("This is the fast Piper voice for the default character.",
                  ref(default), default.tts)
        tts.speak("And this is Hu Tao, in her cloned Chatterbox voice.",
                  ref(hutao), hutao.tts)

    def on_finished() -> None:
        state["finished"] += 1
        print(f"spoken ({state['finished']}/2)")
        if state["finished"] >= 2:
            print("BOTH ENGINES SPOKE — routing + threading hold")
            tts.stop()
            app.quit()

    bus.tts_ready.connect(on_ready)
    bus.tts_started.connect(lambda: print("speaking…"))
    bus.tts_finished.connect(on_finished)

    tts = TTSThread(bus)
    tts.start()

    QTimer.singleShot(300000, app.quit)  # safety timeout
    app.exec()
    return 0 if state["finished"] >= 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
