"""Unit tests for the visualizer easing math (no Qt widget needed)."""
from winter.ui.visualizer import ease


def test_ease_moves_toward_target():
    # one step covers `factor` of the remaining distance
    assert ease(0.0, 1.0, 0.25) == 0.25
    assert ease(0.0, 1.0, 0.5) == 0.5


def test_ease_converges():
    value = 0.0
    for _ in range(100):
        value = ease(value, 1.0, 0.25)
    assert abs(value - 1.0) < 1e-3


def test_ease_at_target_is_stable():
    assert ease(0.7, 0.7, 0.25) == 0.7


def test_ease_handles_downward():
    assert ease(1.0, 0.0, 0.25) == 0.75
