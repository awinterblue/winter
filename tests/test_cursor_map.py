"""Unit tests for the cursor mapping and One-Euro filter."""
from winter.vision.cursor_map import CursorMapper, OneEuroFilter


def test_one_euro_passes_first_value():
    f = OneEuroFilter()
    assert f(5.0, 0.0) == 5.0


def test_one_euro_smooths_jitter():
    f = OneEuroFilter()
    f(0.0, 0.0)
    # a sudden spike should not be followed all the way
    out = f(100.0, 1 / 30)
    assert 0.0 < out < 100.0


def test_one_euro_converges_to_steady_value():
    f = OneEuroFilter()
    value = 0.0
    for i in range(120):
        value = f(50.0, i / 30)
    assert abs(value - 50.0) < 1.0


def test_cursor_mapper_centre():
    mapper = CursorMapper(1000, 800, margin=0.15)
    x, y = mapper.map(0.5, 0.5, 0.0)
    assert abs(x - 500) < 1 and abs(y - 400) < 1


def test_cursor_mapper_active_rect_edges():
    mapper = CursorMapper(1000, 800, margin=0.15)
    # the inset rectangle's corners map to the screen corners
    x0, y0 = mapper.map(0.15, 0.15, 0.0)
    x1, y1 = mapper.map(0.85, 0.85, 1.0)
    assert x0 < 2 and y0 < 2
    assert x1 > 998 and y1 > 798


def test_cursor_mapper_clamps_out_of_range():
    mapper = CursorMapper(1000, 800)
    x, y = mapper.map(-0.5, 1.9, 0.0)
    assert 0 <= x <= 999 and 0 <= y <= 799
