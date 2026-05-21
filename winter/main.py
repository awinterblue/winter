"""Winter entry point."""
from __future__ import annotations

import os
import signal
import sys

# OpenCV tries to request camera permission itself, but fails from a worker
# thread. Skip that — Winter requests camera access on the main thread instead.
os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")
# Windows can't always make Hugging Face cache symlinks — silence the warning.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Winter")
    app.setQuitOnLastWindowClosed(False)  # menu-bar app — no main window

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Winter", "The system tray is not available.")
        return 1

    # let Ctrl+C through the Qt event loop
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    keepalive = QTimer()
    keepalive.start(200)
    keepalive.timeout.connect(lambda: None)

    from winter.app import AppController

    controller = AppController()
    app.aboutToQuit.connect(controller.shutdown)
    controller.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
