"""Unit tests for hand-gesture recognition (synthetic landmarks, no camera)."""
import numpy as np

from winter.vision.gestures import (GestureEngine, hand_pose, is_flat_palm,
                                    pinch_ratio)
from winter.vision.gestures import (INDEX_MCP, INDEX_PIP, INDEX_TIP,
                                    MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP,
                                    PINKY_MCP, PINKY_PIP, PINKY_TIP, RING_PIP,
                                    RING_TIP, THUMB_TIP, WRIST)

# pip joints sit at a fixed mid distance; an extended tip is far from the
# wrist, a curled tip is near it — matching gestures._finger_extended.
_EXT = {INDEX_TIP: (0.57, 0.15), MIDDLE_TIP: (0.50, 0.12),
        RING_TIP: (0.43, 0.15), PINKY_TIP: (0.38, 0.20)}
_CURL = {INDEX_TIP: (0.55, 0.72), MIDDLE_TIP: (0.50, 0.72),
         RING_TIP: (0.45, 0.72), PINKY_TIP: (0.40, 0.72)}
_PIP = {INDEX_PIP: (0.55, 0.55), MIDDLE_PIP: (0.50, 0.55),
        RING_PIP: (0.45, 0.55), PINKY_PIP: (0.40, 0.57)}


def make_hand(index=False, middle=False, ring=False, pinky=False,
              thumb=(0.32, 0.62), center_x=0.5, center_y=0.0):
    """Build a (21, 3) landmark array; center_x/center_y shift the whole hand."""
    dx, dy = center_x - 0.5, center_y
    lm = np.zeros((21, 3))
    lm[WRIST] = (0.5 + dx, 0.90 + dy, 0)
    lm[MIDDLE_MCP] = (0.5 + dx, 0.60 + dy, 0)
    lm[INDEX_MCP] = (0.56 + dx, 0.62 + dy, 0)   # knuckle row — wide when flat
    lm[PINKY_MCP] = (0.38 + dx, 0.64 + dy, 0)
    for pip, xy in _PIP.items():
        lm[pip] = (xy[0] + dx, xy[1] + dy, 0)
    for tip, ext in zip((INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP),
                        (index, middle, ring, pinky)):
        src = _EXT[tip] if ext else _CURL[tip]
        lm[tip] = (src[0] + dx, src[1] + dy, 0)
    lm[THUMB_TIP] = (thumb[0] + dx, thumb[1] + dy, 0)
    return lm


# --- pose classification: only 'pointing' is special; all else flicks ---

def test_pointing_pose():
    assert hand_pose(make_hand(index=True)) == "pointing"


def test_open_hand_is_not_pointing():
    assert hand_pose(make_hand(True, True, True, True)) == "open"


def test_fist_is_not_pointing():
    # a fist is non-pointing, so it is eligible to flick
    assert hand_pose(make_hand()) != "pointing"


# --- cursor tracking ---

def test_pointing_emits_cursor_at_index_tip():
    result = GestureEngine().update(make_hand(index=True), now=0.0)
    assert result.pose == "pointing"
    assert result.cursor is not None


def test_no_hand_emits_nothing():
    result = GestureEngine().update(None, now=0.0)
    assert result.cursor is None and result.pose == "none"


# --- pinch = a single click, no drag ---

def test_pinch_produces_one_click():
    engine = GestureEngine()
    pinched = make_hand(index=True, thumb=(0.57, 0.18))   # thumb on index tip
    events: list[str] = []
    for _ in range(4):                                    # held pinch
        events += engine.update(pinched, now=0.0).events
    assert events.count("click") == 1                     # exactly one, no hold


def test_pinch_release_then_pinch_clicks_again():
    engine = GestureEngine()
    pinched = make_hand(index=True, thumb=(0.57, 0.18))
    released = make_hand(index=True, thumb=(0.32, 0.62))
    events: list[str] = []
    for hand in (pinched, pinched, released, released, pinched, pinched):
        events += engine.update(hand, now=0.0).events
    assert events.count("click") == 2
    assert "click_down" not in events and "click_up" not in events


def test_pinch_ratio_small_when_pinched():
    assert pinch_ratio(make_hand(index=True, thumb=(0.57, 0.16))) < 0.45
    assert pinch_ratio(make_hand(index=True, thumb=(0.32, 0.62))) > 0.65


# --- fast flick: horizontal = swipe, vertical = scroll ---

def test_fast_swipe_right():
    engine = GestureEngine()
    events: list[str] = []
    for i in range(6):
        hand = make_hand(True, True, True, True, center_x=0.30 + i * 0.10)
        events += engine.update(hand, now=i * 0.04).events
    assert "swipe_right" in events


def test_fast_swipe_left():
    engine = GestureEngine()
    events: list[str] = []
    for i in range(6):
        hand = make_hand(True, True, True, True, center_x=0.80 - i * 0.10)
        events += engine.update(hand, now=i * 0.04).events
    assert "swipe_left" in events


# --- flat-palm gate: only a flat open palm may scroll ---

def test_flat_open_palm_detected():
    assert is_flat_palm(make_hand(True, True, True, True))


def test_fist_is_not_a_flat_palm():
    assert not is_flat_palm(make_hand())


def test_edge_on_hand_is_not_a_flat_palm():
    # fingers extended, but the knuckle row is collapsed (hand turned edge-on)
    hand = make_hand(True, True, True, True)
    hand[PINKY_MCP] = hand[INDEX_MCP]
    assert not is_flat_palm(hand)


def test_non_flat_hand_held_low_does_not_scroll():
    # the whole point: a fist (or any non-flat hand) held low must NOT scroll
    engine = GestureEngine()
    events: list[str] = []
    for i in range(12):
        events += engine.update(make_hand(center_y=0.30), now=i * 0.2).events
    assert "scroll_down" not in events


# --- hold-to-scroll: hold a flat open palm above/below its neutral height ---

def test_holding_hand_low_scrolls_down():
    engine = GestureEngine()
    engine.update(make_hand(True, True, True, True, center_y=0.0), now=0.0)  # neutral
    events: list[str] = []
    for i in range(1, 12):
        hand = make_hand(True, True, True, True, center_y=0.22)   # held low
        events += engine.update(hand, now=i * 0.2).events
    assert events.count("scroll_down") >= 2     # repeats while held


def test_holding_hand_high_scrolls_up():
    engine = GestureEngine()
    engine.update(make_hand(True, True, True, True, center_y=0.0), now=0.0)
    events: list[str] = []
    for i in range(1, 12):
        hand = make_hand(True, True, True, True, center_y=-0.22)  # held high
        events += engine.update(hand, now=i * 0.2).events
    assert events.count("scroll_up") >= 2


def test_hand_near_neutral_does_not_scroll():
    engine = GestureEngine()
    engine.update(make_hand(True, True, True, True, center_y=0.0), now=0.0)
    events: list[str] = []
    for i in range(1, 12):
        hand = make_hand(True, True, True, True, center_y=0.04)   # within deadzone
        events += engine.update(hand, now=i * 0.2).events
    assert not events


def test_further_from_neutral_scrolls_faster():
    near, far = GestureEngine(), GestureEngine()
    near.update(make_hand(True, True, True, True, center_y=0.0), now=0.0)
    far.update(make_hand(True, True, True, True, center_y=0.0), now=0.0)
    near_count = far_count = 0
    for i in range(1, 30):
        near_count += near.update(
            make_hand(True, True, True, True, center_y=0.13), now=i * 0.1
        ).events.count("scroll_down")
        far_count += far.update(
            make_hand(True, True, True, True, center_y=0.42), now=i * 0.1
        ).events.count("scroll_down")
    assert far_count > near_count


def test_slow_open_hand_does_not_flick():
    """A slow drift must not count as a swipe — it is purely about speed."""
    engine = GestureEngine()
    events: list[str] = []
    for i in range(10):
        hand = make_hand(True, True, True, True, center_x=0.45 + i * 0.01)
        events += engine.update(hand, now=i * 0.10).events  # slow: 0.1 u/s
    assert not events


def test_still_open_hand_does_not_flick():
    engine = GestureEngine()
    events: list[str] = []
    for i in range(8):
        events += engine.update(make_hand(True, True, True, True),
                                now=i * 0.04).events
    assert not events
