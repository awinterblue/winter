"""Verify the camera + hand-tracking + gesture pipeline.

    .venv/bin/python scripts/verify_camera.py

Opens the webcam, runs the MediaPipe Hand Landmarker and GestureEngine for a
few seconds, and reports what it saw. It does NOT move the real cursor — safe
to run. Wave / point / pinch / open-hand-swipe at the camera while it runs.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

DURATION = 8.0


def main() -> int:
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python.core.base_options import BaseOptions
    from mediapipe.tasks.python.vision import (HandLandmarker,
                                               HandLandmarkerOptions,
                                               RunningMode)

    from winter import MODELS_DIR
    from winter.vision.cursor_map import CursorMapper
    from winter.vision.gestures import GestureEngine

    model = MODELS_DIR / "hand_landmarker.task"
    if not model.exists():
        print(f"FAIL: model missing at {model}")
        return 1

    capture = cv2.VideoCapture(0)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not capture.isOpened():
        print("FAIL: could not open the camera (grant Camera permission?)")
        return 1

    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model)),
        running_mode=RunningMode.VIDEO, num_hands=1,
        min_hand_detection_confidence=0.6, min_tracking_confidence=0.5,
    )
    landmarker = HandLandmarker.create_from_options(options)
    engine = GestureEngine()
    mapper = CursorMapper(1512, 982)

    frames = hand_frames = 0
    poses: dict[str, int] = {}
    events: list[str] = []
    started = time.monotonic()
    print(f"watching for {DURATION:.0f}s — point, pinch, open-hand swipe…")

    while time.monotonic() - started < DURATION:
        ok, frame = capture.read()
        if not ok:
            continue
        frames += 1
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        now = time.monotonic()
        result = landmarker.detect_for_video(image, int(now * 1000))

        landmarks = None
        if result.hand_landmarks:
            hand_frames += 1
            landmarks = np.array([[p.x, p.y, p.z]
                                  for p in result.hand_landmarks[0]])
        gesture = engine.update(landmarks, now)
        poses[gesture.pose] = poses.get(gesture.pose, 0) + 1
        if gesture.cursor is not None:
            mapper.map(gesture.cursor[0], gesture.cursor[1], now)  # exercise it
        for event in gesture.events:
            events.append(event)
            print(f"  gesture: {event}")

    capture.release()
    landmarker.close()

    fps = frames / DURATION
    print(f"\nframes: {frames} ({fps:.1f} fps), hand seen in {hand_frames}")
    print(f"poses: {poses}")
    print(f"gestures fired: {events or 'none'}")
    ok = frames > 30 and fps > 10
    print("CAMERA VERIFY " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
