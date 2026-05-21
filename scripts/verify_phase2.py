"""Headless functional check for Phase 2 — web Q&A, in-character replies, TTS.

    .venv/bin/python scripts/verify_phase2.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class _FakeBus:
    """Stand-in for the EventBus — router only emits status_message."""

    class _Signal:
        def emit(self, *args):
            pass

    status_message = _Signal()


def main() -> int:
    from winter.config.character import CharacterManager
    from winter.config.settings import Settings

    settings = Settings.load()
    manager = CharacterManager()
    character = manager.get("hutao") or manager.active
    print(f"character: {character.display_name}")

    print("\n== web search (ddgs) ==")
    from winter.brain.websearch import DdgsProvider
    search = DdgsProvider()
    started = time.time()
    results = search.search("how tall is mount everest", max_results=4)
    print(f"  {len(results)} results in {time.time() - started:.2f}s")
    for item in results[:2]:
        print(f"   - {item[:90]}")

    print("\n== in-character answer (web + LLM) ==")
    from winter.brain.llm import OllamaClient
    llm = OllamaClient(settings.llm.model, settings.llm.host)
    started = time.time()
    answer = llm.answer(character.personality_prompt,
                        "how tall is mount everest", results)
    print(f"  ({time.time() - started:.2f}s) {answer!r}")

    print("\n== in-character chit-chat ==")
    started = time.time()
    reply = llm.roleplay(character.personality_prompt, "hi, who are you?")
    print(f"  ({time.time() - started:.2f}s) {reply!r}")

    print("\n== full router (question -> spoken answer) ==")
    from winter.brain.router import IntentRouter
    router = IntentRouter(llm, search, _FakeBus())
    started = time.time()
    route = router.handle("what is the capital of Japan", character)
    print(f"  ({time.time() - started:.2f}s) display={route.display!r}")
    print(f"  will speak: {route.speak is not None}")

    print("\n== text-to-speech (Chatterbox) ==")
    import soundfile as sf
    from winter.audio.tts import ChatterboxEngine

    print("  loading model (first run downloads ~2 GB)…")
    started = time.time()
    tts = ChatterboxEngine()
    print(f"  loaded on '{tts.device}' in {time.time() - started:.1f}s, "
          f"sample rate {tts.sample_rate}")
    reference = character.voice_reference if character.has_voice_reference else None
    print(f"  voice reference: {'yes' if reference else 'no — default voice'}")
    started = time.time()
    audio = tts.synthesize(
        "Hello! I am Hu Tao, and I will be your guide today.",
        reference, character.tts,
    )
    out = Path("/tmp/winter_tts_test.wav")
    sf.write(str(out), audio, tts.sample_rate)
    duration = len(audio) / tts.sample_rate
    print(f"  synthesized {duration:.1f}s of audio in "
          f"{time.time() - started:.1f}s -> {out}")

    print("\nALL PHASE 2 CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
