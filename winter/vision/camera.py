"""Camera capture + hand tracking on its own QThread.

Reads the webcam, runs the MediaPipe Hand Landmarker, and turns landmarks into
cursor moves and discrete gestures, delivered through the EventBus.
"""
from __future__ import annotations

import time

import numpy as np
from PyQt6.QtCore import QThread

from winter.assets import HAND_MODEL, ensure_hand_model
from winter.system.osinfo import IS_WINDOWS
from winter.vision.cursor_map import CursorMapper
from winter.vision.gestures import GestureEngine


class CameraThread(QThread):
    def __init__(self, bus, settings, parent=None):
        super().__init__(parent)
        self.bus = bus
        self.settings = settings
        self._running = False

    def stop(self) -> None:
        self._running = False
        self.wait(4000)

    def run(self) -> None:
        try:
            self._loop()
        except ImportError as exc:
            self.bus.error.emit(
                f"Camera gestures need 'mediapipe' and 'opencv-python' ({exc})."
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            self.bus.error.emit(f"Camera failed: {exc}")

    def _loop(self) -> None:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks.python.core.base_options import BaseOptions
        from mediapipe.tasks.python.vision import (HandLandmarker,
                                                   HandLandmarkerOptions,
                                                   RunningMode)
        from winter.system import cursor

        try:
            ensure_hand_model()        # download it on first run if missing
        except Exception as exc:  # noqa: BLE001
            self.bus.error.emit(f"Hand-tracking model unavailable: {exc}")
            return

        cam = self.settings.camera
        # On Windows the DirectShow backend is far more reliable than the
        # default (MSMF) for opening a webcam.
        if IS_WINDOWS:
            capture = cv2.VideoCapture(cam.index, cv2.CAP_DSHOW)
        else:
            capture = cv2.VideoCapture(cam.index)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, cam.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, cam.height)
        if not capture.isOpened():
            self.bus.error.emit(
                "Could not open the camera — make sure no other app is using "
                "it, and that the OS lets desktop apps access the camera."
            )
            return

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(HAND_MODEL)),
            running_mode=RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_tracking_confidence=0.5,
        )
        landmarker = HandLandmarker.create_from_options(options)
        engine = GestureEngine()
        screen_w, screen_h = cursor.screen_size()
        mapper = CursorMapper(screen_w, screen_h)

        self._running = True
        self.bus.status_message.emit("Camera gestures on — point to move, "
                                     "pinch to click, open-hand swipe.")
        had_hand = False
        try:
            while self._running:
                ok, frame = capture.read()
                if not ok:
                    time.sleep(0.01)
                    continue
                frame = cv2.flip(frame, 1)  # mirror for natural movement
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                now = time.monotonic()
                result = landmarker.detect_for_video(image, int(now * 1000))

                landmarks = None
                if result.hand_landmarks:
                    landmarks = np.array(
                        [[p.x, p.y, p.z] for p in result.hand_landmarks[0]]
                    )

                if (landmarks is not None) != had_hand:
                    had_hand = landmarks is not None
                    if not had_hand:
                        mapper.reset()

                gesture = engine.update(landmarks, now)
                if gesture.cursor is not None:
                    sx, sy = mapper.map(gesture.cursor[0], gesture.cursor[1], now)
                    self.bus.cursor_target.emit(sx, sy)
                for event in gesture.events:
                    self.bus.gesture_detected.emit(event)
        finally:
            capture.release()
            landmarker.close()
