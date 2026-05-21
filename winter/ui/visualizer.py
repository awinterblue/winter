"""Winter's on-screen character — an animated sprite.

Evolved from the audio visualizer: a friendly round creature that floats on
screen and reacts to what Winter is doing. It blinks, glances around, bobs
gently, hops when it starts listening, and its mouth moves while it speaks.

Transparent, always-on-top, draggable. Kept behind set_level/set_state so the
rest of the app neither knows nor cares that the orb grew a face.
"""
from __future__ import annotations

import math
import random
import time
from typing import Callable, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (QColor, QGuiApplication, QPainter, QPen, QPixmap,
                         QRadialGradient)
from PyQt6.QtWidgets import QWidget

# one colour per app phase — the body tints to show what Winter is doing
_STATE_COLORS = {
    "idle": QColor(120, 180, 255),      # calm blue
    "listening": QColor(110, 220, 150),  # green
    "thinking": QColor(255, 200, 90),   # amber
    "speaking": QColor(200, 140, 240),  # purple
}
_EYE_COLOR = QColor(40, 45, 70)
_CHEEK_COLOR = QColor(255, 150, 170)


def ease(current: float, target: float, factor: float = 0.25) -> float:
    """Move `current` a fraction of the way toward `target` (exponential ease)."""
    return current + (target - current) * factor


class VisualizerWidget(QWidget):
    """An animated character sprite. `set_level`/`set_state` drive its mood."""

    def __init__(self, settings, on_move: Optional[Callable[[int, int], None]] = None):
        super().__init__()
        self._vs = settings.visualizer
        self._on_move = on_move

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setToolTip("Winter — drag to move")

        size = max(80, int(self._vs.size))
        self.resize(size, size)
        self._restore_position()

        self._level = 0.0           # smoothed audio level
        self._target_level = 0.0
        self._state = "idle"
        self._drag_offset: Optional[QPointF] = None
        # per-character art: state -> QPixmap. empty = use the code-drawn sprite
        self._pixmaps: dict[str, QPixmap] = {}

        now = time.monotonic()
        self._t0 = now
        # blink
        self._blink = 0.0           # 0 open .. 1 shut
        self._blink_start = 0.0
        self._next_blink = now + random.uniform(2.0, 4.0)
        # glance
        self._look = [0.0, 0.0]
        self._look_target = [0.0, 0.0]
        self._next_look = now + random.uniform(2.0, 5.0)
        # hop
        self._hop_start = -10.0
        # audio-reactive aura — expanding 'sound wave' ripples while speaking
        self._ripples: list[float] = []
        self._last_ripple = 0.0
        # the macOS window shadow goes stale when the sprite changes shape —
        # recompute it for a short burst after the sprite appears/changes
        self._shadow_refresh_until = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)       # ~60 fps

    # ------------------------------------------------------------- positioning
    def _restore_position(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = self._vs.x if self._vs.x is not None \
            else screen.right() - self.width() - 40
        y = self._vs.y if self._vs.y is not None \
            else screen.bottom() - self.height() - 60
        x = max(screen.left(), min(int(x), screen.right() - self.width()))
        y = max(screen.top(), min(int(y), screen.bottom() - self.height()))
        self.move(x, y)

    def show_orb(self) -> None:
        """Show the sprite, re-clamped on-screen and raised above other windows."""
        self._restore_position()
        self.show()
        self.raise_()
        self._shadow_refresh_until = time.monotonic() + 0.7

    def _refresh_shadow(self) -> None:
        """Ask macOS to recompute this window's drop shadow for the current
        content — otherwise it keeps the previous sprite's silhouette."""
        from winter.system.osinfo import IS_MACOS

        if not IS_MACOS:
            return   # the stale-shadow quirk is macOS-only
        try:
            import objc

            view = objc.objc_object(c_void_p=int(self.winId()))
            window = view.window()
            if window is not None:
                window.invalidateShadow()
        except Exception:  # noqa: BLE001 - cosmetic; never break the UI
            pass

    # -------------------------------------------------------------- public API
    def set_level(self, level: float) -> None:
        self._target_level = max(0.0, min(1.0, float(level)))

    def set_state(self, state: str) -> None:
        if state not in _STATE_COLORS or state == self._state:
            return
        if state == "listening":
            self.play_action("hop")     # perk up when it starts listening
        self._state = state
        if state != "speaking":
            self._target_level = 0.0

    def play_action(self, name: str) -> None:
        if name == "hop":
            self._hop_start = time.monotonic()

    def set_character(self, character) -> None:
        """Load this character's sprite art; falls back to the code-drawn
        sprite when the character has no images."""
        self._pixmaps = {}
        for state in _STATE_COLORS:
            path = character.sprite_image(state) if character else None
            if path is not None:
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    self._pixmaps[state] = pixmap
        self.update()
        # the new sprite is a different shape — refresh the shadow once it paints
        self._shadow_refresh_until = time.monotonic() + 0.7

    # ----------------------------------------------------------------- animate
    def _tick(self) -> None:
        now = time.monotonic()
        self._level = ease(self._level, self._target_level, 0.25)

        # blink: a quick triangle 0 -> 1 -> 0 lasting ~0.16 s
        if self._blink == 0.0 and now >= self._next_blink:
            self._blink_start = now
            self._blink = 1e-6
        if self._blink > 0.0:
            phase = (now - self._blink_start) / 0.16
            if phase >= 1.0:
                self._blink = 0.0
                self._next_blink = now + random.uniform(2.0, 5.0)
            else:
                self._blink = 1.0 - abs(2.0 * phase - 1.0)

        # glance: pick a new target now and then, ease toward it
        if now >= self._next_look:
            if self._look_target == [0.0, 0.0]:
                self._look_target = [random.uniform(-1, 1), random.uniform(-0.6, 0.6)]
            else:
                self._look_target = [0.0, 0.0]
            self._next_look = now + random.uniform(1.4, 3.5)
        self._look[0] = ease(self._look[0], self._look_target[0], 0.12)
        self._look[1] = ease(self._look[1], self._look_target[1], 0.12)

        # aura ripples: spawn while there is voice, expand and fade
        if self._level > 0.30:
            interval = 0.5 - 0.3 * self._level   # louder voice -> faster waves
            if now - self._last_ripple > interval:
                self._ripples.append(0.0)
                self._last_ripple = now
        # advance ripples; drop any that have reached the edge (progress >= 1)
        self._ripples = [p + 0.018 for p in self._ripples if p + 0.018 < 1.0]

        self.update()

        # for a short burst after the sprite changes, keep the macOS shadow
        # in sync with the freshly-painted content
        if now < self._shadow_refresh_until:
            self._refresh_shadow()

    def _hop_offset(self, now: float) -> float:
        """Upward pixel offset from an in-progress hop, 0 when not hopping."""
        phase = (now - self._hop_start) / 0.45
        if 0.0 <= phase <= 1.0:
            return math.sin(phase * math.pi) * (self.width() * 0.10)
        return 0.0

    # ------------------------------------------------------------------- paint
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        now = time.monotonic()
        t = now - self._t0
        size = self.width()
        cx = size / 2
        color = _STATE_COLORS[self._state]
        level = self._level

        # gentle idle bob + a hop, shared by both the art and code-drawn sprites
        bob = math.sin(t * 2.2) * size * 0.022
        hop = self._hop_offset(now)
        cy = size / 2 - bob - hop

        # soft state-coloured glow — fixed at the widget centre so it fades to
        # nothing exactly at the edges and never gets a hard-clipped border
        centre = QPointF(size / 2, size / 2)
        glow = QRadialGradient(centre, size * 0.5)
        inner = QColor(color)
        inner.setAlpha(int(70 + 110 * level))
        faded = QColor(color)
        faded.setAlpha(0)
        glow.setColorAt(0.0, inner)
        glow.setColorAt(1.0, faded)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(centre, size * 0.5, size * 0.5)

        # audio-reactive aura framing the sprite
        self._draw_aura(painter, cx, cy, size, color, level, t)

        if self._pixmaps:
            self._draw_image_sprite(painter, cx, cy, size, level)
        else:
            self._draw_code_sprite(painter, cx, cy, size, t, level)

    def _draw_aura(self, painter: QPainter, cx: float, cy: float, size: int,
                   color: QColor, level: float, t: float) -> None:
        """Pulsing rings + expanding sound-wave ripples behind the sprite."""
        painter.setBrush(Qt.BrushStyle.NoBrush)

        base_r = size * 0.21
        edge_r = size * 0.34
        breath = math.sin(t * 1.6) * 0.03
        # three rings that pulse out with the voice
        for i in range(3):
            spread = (i + 1) / 3 * (0.42 + 0.58 * level) + breath
            ring_r = base_r + (edge_r - base_r) * min(1.0, spread)
            ring = QColor(color)
            ring.setAlpha(max(0, int((120 - i * 32) * (0.28 + 0.72 * level))))
            painter.setPen(QPen(ring, 2.0 + 1.6 * level))
            painter.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

        # ripples emanating outward while speaking
        for progress in self._ripples:
            ripple_r = base_r + (edge_r - base_r) * progress
            ring = QColor(color)
            ring.setAlpha(max(0, min(255, int(170 * (1.0 - progress)))))
            painter.setPen(QPen(ring, 2.4))
            painter.drawEllipse(QPointF(cx, cy), ripple_r, ripple_r)

    def _draw_image_sprite(self, painter: QPainter, cx: float, cy: float,
                           size: int, level: float) -> None:
        """Draw this character's artwork for the current state."""
        pixmap = self._pixmaps.get(self._state) or next(iter(self._pixmaps.values()))
        # leave margin so the bob/hop never clips the sprite against the edge
        scale = 0.66 + (0.03 * level if self._state == "speaking" else 0.0)
        avail = int(size * scale)
        scaled = pixmap.scaled(
            avail, avail,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(int(cx - scaled.width() / 2),
                           int(cy - scaled.height() / 2), scaled)

    def _draw_code_sprite(self, painter: QPainter, cx: float, cy: float,
                          size: int, t: float, level: float) -> None:
        """Winter's built-in code-drawn character (the fallback sprite)."""
        color = _STATE_COLORS[self._state]
        squash = 1.0 - math.sin(t * 2.2) * 0.04 + level * 0.05
        body_w = size * 0.56
        body_h = size * 0.56 * squash

        body = QRadialGradient(cx - body_w * 0.22, cy - body_h * 0.3, body_w)
        body.setColorAt(0.0, QColor(color).lighter(155))
        body.setColorAt(1.0, color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(body)
        painter.drawEllipse(QPointF(cx, cy), body_w / 2, body_h / 2)

        self._draw_face(painter, cx, cy, body_w, body_h, level)

    def _draw_face(self, painter: QPainter, cx: float, cy: float,
                   body_w: float, body_h: float, level: float) -> None:
        eye_dx = body_w * 0.20
        eye_y = cy - body_h * 0.06
        eye_w = body_w * 0.17
        eye_h = body_h * 0.24 * (1.0 - 0.92 * self._blink)
        look_x = self._look[0] * body_w * 0.05
        look_y = self._look[1] * body_h * 0.05
        if self._state == "thinking":      # eyes drift up while it thinks
            look_y -= body_h * 0.05
        if self._state == "listening":     # eyes widen, alert
            eye_h *= 1.15

        for sign in (-1, 1):
            ex = cx + sign * eye_dx + look_x
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_EYE_COLOR)
            painter.drawEllipse(QPointF(ex, eye_y + look_y), eye_w / 2, eye_h / 2)
            if self._blink < 0.5:          # a shine dot, hidden mid-blink
                painter.setBrush(QColor(255, 255, 255, 230))
                shine = eye_w * 0.20
                painter.drawEllipse(
                    QPointF(ex - eye_w * 0.16, eye_y + look_y - eye_h * 0.20),
                    shine, shine,
                )

        # blush cheeks — friendlier when idle or speaking
        if self._state in ("idle", "speaking"):
            painter.setBrush(QColor(_CHEEK_COLOR.red(), _CHEEK_COLOR.green(),
                                    _CHEEK_COLOR.blue(), 120))
            for sign in (-1, 1):
                painter.drawEllipse(
                    QPointF(cx + sign * body_w * 0.30, cy + body_h * 0.12),
                    body_w * 0.085, body_h * 0.055,
                )

        # mouth
        painter.setPen(Qt.PenStyle.NoPen)
        mouth_y = cy + body_h * 0.20
        if self._state == "speaking":
            open_h = body_h * (0.04 + 0.22 * level)
            painter.setBrush(QColor(60, 35, 60))
            painter.drawEllipse(QPointF(cx, mouth_y),
                                body_w * 0.11, max(1.0, open_h))
        else:
            painter.setPen(_EYE_COLOR)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = painter.pen()
            pen.setWidthF(max(1.6, body_w * 0.035))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            mw = body_w * 0.26
            rect = QRectF(cx - mw / 2, mouth_y - body_h * 0.08, mw, body_h * 0.16)
            if self._state == "thinking":
                painter.drawArc(rect, 0, 180 * 16)        # small neutral curve
            else:
                painter.drawArc(rect, 200 * 16, 140 * 16)  # smile

    # -------------------------------------------------------------- drag-to-move
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition() - QPointF(self.pos())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None:
            self.move((event.globalPosition() - self._drag_offset).toPoint())

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None:
            self._drag_offset = None
            if self._on_move:
                self._on_move(self.x(), self.y())
