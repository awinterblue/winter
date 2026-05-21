"""Show the visualizer and drive it through every state + a fake audio pulse.

    .venv/bin/python scripts/verify_visualizer.py

A window appears: it idles (blue), cycles listening/thinking, then 'speaks'
with a pulsing level for a few seconds, then quits. Drag it to test dragging.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


def main() -> int:
    app = QApplication(sys.argv)

    from winter.config.settings import Settings
    from winter.ui.visualizer import VisualizerWidget

    settings = Settings.load()
    moved = {}
    viz = VisualizerWidget(settings, on_move=lambda x, y: moved.update(x=x, y=y))
    viz.show_orb()
    print(f"visualizer shown at {viz.pos().x()},{viz.pos().y()} — drag to test")

    # scripted demo: state changes, then a pulsing 'speaking' level
    QTimer.singleShot(1200, lambda: (print("-> listening"), viz.set_state("listening")))
    QTimer.singleShot(2400, lambda: (print("-> thinking"), viz.set_state("thinking")))
    QTimer.singleShot(3600, lambda: (print("-> speaking"), viz.set_state("speaking")))

    frame = {"n": 0}
    pulse = QTimer()

    def feed_level() -> None:
        frame["n"] += 1
        if frame["n"] > 120:               # ~6 s of pulsing
            pulse.stop()
            viz.set_state("idle")
            print("-> idle; quitting shortly")
            QTimer.singleShot(1500, app.quit)
            return
        viz.set_level(0.5 + 0.5 * math.sin(frame["n"] * 0.3))

    pulse.timeout.connect(feed_level)
    QTimer.singleShot(3600, lambda: pulse.start(50))

    QTimer.singleShot(30000, app.quit)     # safety timeout
    app.exec()
    print(f"final position: {moved or 'not dragged'}")
    print("VISUALIZER VERIFY DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
