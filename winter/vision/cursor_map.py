"""Map a fingertip in the camera frame to a smoothed screen position."""
from __future__ import annotations

import math


class OneEuroFilter:
    """The 1€ filter — low jitter when still, low lag when moving fast.

    See Casiez et al., 2012. `min_cutoff` sets the smoothing floor; `beta`
    sets how much fast motion sharpens the response.
    """

    def __init__(self, min_cutoff: float = 1.2, beta: float = 0.6,
                 d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x_prev: float | None = None
        self._dx_prev = 0.0
        self._t_prev: float | None = None

    @staticmethod
    def _alpha(cutoff: float, freq: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        te = 1.0 / freq
        return 1.0 / (1.0 + tau / te)

    def __call__(self, x: float, t: float) -> float:
        if self._t_prev is None or t <= self._t_prev:
            self._t_prev = t
            self._x_prev = x
            return x
        freq = 1.0 / (t - self._t_prev)
        dx = (x - self._x_prev) * freq
        a_d = self._alpha(self.d_cutoff, freq)
        dx_hat = a_d * dx + (1 - a_d) * self._dx_prev
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, freq)
        x_hat = a * x + (1 - a) * self._x_prev
        self._x_prev = x_hat
        self._dx_prev = dx_hat
        self._t_prev = t
        return x_hat


class CursorMapper:
    """Normalized fingertip (0-1, already mirrored) -> smoothed screen pixels.

    Only an inset rectangle of the frame maps to the screen, so the user can
    reach every corner without stretching to the camera's edges.
    """

    def __init__(self, screen_w: float, screen_h: float, margin: float = 0.15):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.margin = margin
        self._fx = OneEuroFilter()
        self._fy = OneEuroFilter()

    def map(self, nx: float, ny: float, t: float) -> tuple[float, float]:
        span = 1.0 - 2 * self.margin
        u = min(1.0, max(0.0, (nx - self.margin) / span))
        v = min(1.0, max(0.0, (ny - self.margin) / span))
        sx = self._fx(u * self.screen_w, t)
        sy = self._fy(v * self.screen_h, t)
        sx = min(self.screen_w - 1, max(0.0, sx))
        sy = min(self.screen_h - 1, max(0.0, sy))
        return sx, sy

    def reset(self) -> None:
        """Forget motion history — call when the hand leaves and returns."""
        self._fx = OneEuroFilter()
        self._fy = OneEuroFilter()
