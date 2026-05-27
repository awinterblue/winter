"""Hand-gesture recognition from MediaPipe landmarks.

Pose-gated so the modes never fight:
  - a pointing finger drives the cursor and pinch-clicks;
  - any other hand shape flicked sideways does a swipe (prev/next track);
  - any other hand held above/below its neutral height scrolls continuously.

Works on a plain (21, 3) numpy array of normalized landmarks, so it is fully
testable without a camera.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# MediaPipe hand landmark indices
WRIST = 0
THUMB_TIP = 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_PIP, RING_TIP = 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20

# pinch (thumb tip <-> index tip, normalized by hand size) with hysteresis
_PINCH_ON = 0.45
_PINCH_OFF = 0.65
_PINCH_DEBOUNCE = 2

# horizontal swipe — a fast sideways flick of a non-pointing hand
_SWIPE_WINDOW = 0.35      # seconds of position history kept
_SWIPE_MIN_DT = 0.05      # shortest interval used for a velocity estimate
_SWIPE_MAX_DT = 0.32      # longest interval used
_SWIPE_SPEED = 1.0       # normalized units/sec the hand must exceed
_SWIPE_MIN_TRAVEL = 0.09  # min horizontal travel (ignores twitches)
_SWIPE_COOLDOWN = 0.5

# scroll requires a deliberate FLAT OPEN PALM facing the camera, so casual
# hand movements never scroll by accident
_FLAT_PALM_SPREAD = 0.45    # knuckle-row width / hand size: low = edge-on

# vertical scroll — HOLD a flat open palm above/below its neutral height.
# Neutral is captured wherever the hand first appears, so it is independent of
# camera framing. Scroll repeats while held; further from neutral = faster.
_SCROLL_DEADZONE = 0.10      # move this far from neutral before scrolling
_SCROLL_RANGE = 0.22        # extra travel beyond the dead zone for top speed
_SCROLL_SLOW_INTERVAL = 0.70  # seconds between scrolls just past the dead zone
_SCROLL_FAST_INTERVAL = 0.18  # seconds between scrolls at full extension


def _dist(a, b) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def _finger_extended(lm: np.ndarray, tip: int, pip: int) -> bool:
    """A finger is extended if its tip is farther from the wrist than its
    middle joint — orientation-independent, unlike a simple y-comparison."""
    wrist = lm[WRIST]
    return _dist(lm[tip], wrist) > _dist(lm[pip], wrist)


def is_pointing(lm: np.ndarray) -> bool:
    """True when only the index finger is extended (cursor mode)."""
    index = _finger_extended(lm, INDEX_TIP, INDEX_PIP)
    middle = _finger_extended(lm, MIDDLE_TIP, MIDDLE_PIP)
    ring = _finger_extended(lm, RING_TIP, RING_PIP)
    pinky = _finger_extended(lm, PINKY_TIP, PINKY_PIP)
    return index and not middle and not ring and not pinky


def hand_pose(lm: np.ndarray) -> str:
    """Coarse pose label — 'pointing' drives the cursor, anything else flicks."""
    return "pointing" if is_pointing(lm) else "open"


def is_flat_palm(lm: np.ndarray) -> bool:
    """True for an open, flat palm presented to the camera: every finger
    extended and the knuckle row spread wide (not curled, not edge-on)."""
    if not (_finger_extended(lm, INDEX_TIP, INDEX_PIP)
            and _finger_extended(lm, MIDDLE_TIP, MIDDLE_PIP)
            and _finger_extended(lm, RING_TIP, RING_PIP)
            and _finger_extended(lm, PINKY_TIP, PINKY_PIP)):
        return False
    hand_size = _dist(lm[WRIST], lm[MIDDLE_MCP]) or 1e-6
    spread = _dist(lm[INDEX_MCP], lm[PINKY_MCP])
    return spread / hand_size > _FLAT_PALM_SPREAD


def pinch_ratio(lm: np.ndarray) -> float:
    """Thumb-tip to index-tip distance, normalized by hand size."""
    hand_size = _dist(lm[WRIST], lm[MIDDLE_MCP]) or 1e-6
    return _dist(lm[THUMB_TIP], lm[INDEX_TIP]) / hand_size


@dataclass
class GestureResult:
    pose: str = "none"
    cursor: Optional[tuple[float, float]] = None   # normalized index-tip x,y
    events: list[str] = field(default_factory=list)
    # events: "click", "swipe_left", "swipe_right", "scroll_up", "scroll_down"


class GestureEngine:
    """Feed it landmarks per frame; it returns cursor target + discrete events."""

    def __init__(self) -> None:
        self._pinched = False
        self._pinch_frames = 0
        self._swipe_hist: deque = deque()
        self._swipe_cooldown_until = 0.0
        self._scroll_center: Optional[float] = None
        self._scroll_next = 0.0

    def update(self, landmarks: Optional[np.ndarray],
               now: Optional[float] = None) -> GestureResult:
        now = time.monotonic() if now is None else now
        result = GestureResult()
        if landmarks is None:
            self._reset()
            return result

        # pinch fires whenever the index is extended — the natural pinch motion
        # often briefly extends the middle finger too, which would break the
        # strict 'pointing' pose and lose the click. Decoupling the click from
        # the strict pose keeps it reliable across that flicker.
        if _finger_extended(landmarks, INDEX_TIP, INDEX_PIP):
            self._update_pinch(landmarks, result)
        else:
            self._pinched = False
            self._pinch_frames = 0

        if is_pointing(landmarks):
            # cursor mode — never flick/scroll, so cursor moves stay cursor moves
            result.pose = "pointing"
            self._swipe_hist.clear()
            self._scroll_center = None
            tip = landmarks[INDEX_TIP]
            result.cursor = (float(tip[0]), float(tip[1]))
        else:
            # any non-pointing hand can swipe sideways; only a flat open palm
            # held high/low scrolls — so other hand shapes never scroll
            result.pose = "flick"
            self._update_swipe(landmarks, now, result)
            if is_flat_palm(landmarks):
                self._update_scroll(landmarks, now, result)
            else:
                self._scroll_center = None
                self._scroll_next = 0.0
        return result

    def _reset(self) -> None:
        self._pinched = False
        self._pinch_frames = 0
        self._swipe_hist.clear()
        self._scroll_center = None

    # --- pinch -> a single click (no hold/drag) ---
    def _update_pinch(self, lm: np.ndarray, result: GestureResult) -> None:
        ratio = pinch_ratio(lm)
        if not self._pinched:
            if ratio < _PINCH_ON:
                self._pinch_frames += 1
                if self._pinch_frames >= _PINCH_DEBOUNCE:
                    self._pinched = True
                    self._pinch_frames = 0
                    result.events.append("click")   # one click per pinch
            else:
                self._pinch_frames = 0
        else:
            # wait for the fingers to part again before another click can fire
            if ratio > _PINCH_OFF:
                self._pinch_frames += 1
                if self._pinch_frames >= _PINCH_DEBOUNCE:
                    self._pinched = False
                    self._pinch_frames = 0
            else:
                self._pinch_frames = 0

    # --- horizontal swipe: a fast sideways flick ---
    def _update_swipe(self, lm: np.ndarray, now: float,
                      result: GestureResult) -> None:
        if now < self._swipe_cooldown_until:
            return
        x_now = float(lm[WRIST][0])
        self._swipe_hist.append((now, x_now))
        while self._swipe_hist and now - self._swipe_hist[0][0] > _SWIPE_WINDOW:
            self._swipe_hist.popleft()
        # compare 'now' against every earlier sample — any fast segment fires
        for t0, x0 in list(self._swipe_hist)[:-1]:
            dt = now - t0
            if dt < _SWIPE_MIN_DT or dt > _SWIPE_MAX_DT:
                continue
            dx = x_now - x0
            if abs(dx) / dt > _SWIPE_SPEED and abs(dx) > _SWIPE_MIN_TRAVEL:
                result.events.append("swipe_right" if dx > 0 else "swipe_left")
                self._swipe_cooldown_until = now + _SWIPE_COOLDOWN
                self._swipe_hist.clear()
                return

    # --- vertical scroll: HOLD the hand above/below its neutral height ---
    def _update_scroll(self, lm: np.ndarray, now: float,
                       result: GestureResult) -> None:
        y = float(lm[WRIST][1])
        if self._scroll_center is None:
            # wherever the hand first appears becomes the neutral height
            self._scroll_center = y
            return
        offset = y - self._scroll_center
        past_deadzone = abs(offset) - _SCROLL_DEADZONE
        if past_deadzone <= 0:
            self._scroll_next = 0.0   # back in the dead zone — reset the timer
            return
        if self._scroll_next == 0.0:
            self._scroll_next = now   # entered the zone — scroll immediately
        if now >= self._scroll_next:
            # y grows downward — hand held low scrolls down
            result.events.append("scroll_down" if offset > 0 else "scroll_up")
            frac = min(1.0, past_deadzone / _SCROLL_RANGE)
            interval = (_SCROLL_SLOW_INTERVAL
                        + frac * (_SCROLL_FAST_INTERVAL - _SCROLL_SLOW_INTERVAL))
            self._scroll_next = now + interval
