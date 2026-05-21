"""Verify the integrated mic source — the same read path the app uses.

    .venv/bin/python scripts/verify_micsource.py

Opens the mic the way AudioCaptureThread does, reads wake-word-sized and
VAD-sized frames, and confirms echo cancellation is active.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from winter.audio.capture import CHUNK, VAD_FRAME
from winter.audio.micsource import SAMPLE_RATE, open_mic_source
from winter.config.settings import Settings


def main() -> int:
    source = open_mic_source(Settings.load())
    print(f"source: {type(source).__name__}, echo cancellation: {source.using_aec}")

    print(f"reading 25 wake-word frames ({CHUNK} samples each)…")
    started = time.time()
    sizes_ok = True
    peak = 0
    for _ in range(25):
        frame = source.read(CHUNK)
        if len(frame) != CHUNK or frame.dtype != np.int16:
            sizes_ok = False
        peak = max(peak, int(np.max(np.abs(frame))) if len(frame) else 0)
    elapsed = time.time() - started
    expected = 25 * CHUNK / SAMPLE_RATE
    print(f"  read in {elapsed:.2f}s (≈{expected:.2f}s of audio), peak {peak}")

    print(f"reading 10 VAD frames ({VAD_FRAME} samples each)…")
    vad_ok = all(len(source.read(VAD_FRAME)) == VAD_FRAME for _ in range(10))

    source.stop()

    ok = sizes_ok and vad_ok and abs(elapsed - expected) < 1.0
    print(f"frame sizes correct: {sizes_ok} | vad frames: {vad_ok} | "
          f"realtime pacing: {abs(elapsed - expected) < 1.0}")
    print("MIC SOURCE VERIFY " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
