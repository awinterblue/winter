"""Construct the Qt app + tray without starting the mic, then quit.

    .venv/bin/python scripts/smoke_gui.py

Catches Qt/wiring errors without triggering model loads or mic permissions.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    print("system tray available:", QSystemTrayIcon.isSystemTrayAvailable())

    from winter.app import AppController

    controller = AppController()
    print("AppController constructed OK")
    print("  tray icon visible:", controller.tray.icon.isVisible())
    print("  character menu:", [a.text() for a in controller.tray._char_group.actions()])
    print("  active character:", controller.characters.active.display_name)

    QTimer.singleShot(600, app.quit)
    app.exec()
    controller.shutdown()
    print("GUI SMOKE TEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
