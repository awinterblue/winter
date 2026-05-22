"""Menu-bar (system tray) UI: status line, toggles, character picker, quit."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


def _make_icon(color: str = "#7bd8ff") -> QIcon:
    pixmap = QPixmap(22, 22)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(3, 3, 16, 16)
    painter.end()
    return QIcon(pixmap)


class TrayController:
    """Owns the QSystemTrayIcon and wires its menu to the AppController."""

    def __init__(self, controller):
        self.controller = controller
        self.bus = controller.bus

        self.icon = QSystemTrayIcon(_make_icon())
        self.icon.setToolTip("Winter")

        self.menu = QMenu()
        self._status = QAction("Starting…", self.menu)
        self._status.setEnabled(False)
        self.menu.addAction(self._status)
        self.menu.addSeparator()

        self._voice = QAction("Voice commands", self.menu)
        self._voice.setCheckable(True)
        self._voice.setChecked(controller.state.voice_enabled)
        self._voice.toggled.connect(controller.set_voice_enabled)
        self.menu.addAction(self._voice)

        self._camera = QAction("Camera commands", self.menu)
        self._camera.setCheckable(True)
        self._camera.setChecked(controller.state.camera_enabled)
        self._camera.toggled.connect(controller.set_camera_enabled)
        self.menu.addAction(self._camera)

        self._visualizer = QAction("Show visualizer", self.menu)
        self._visualizer.setCheckable(True)
        self._visualizer.setChecked(controller.settings.visualizer.enabled)
        self._visualizer.toggled.connect(controller.set_visualizer_visible)
        self.menu.addAction(self._visualizer)

        self.menu.addSeparator()
        self._char_menu = self.menu.addMenu("Character")
        self._char_group = QActionGroup(self.menu)
        self._char_group.setExclusive(True)
        self.refresh_characters()

        create_action = QAction("Create Character…", self.menu)
        create_action.triggered.connect(controller.open_create_character)
        self.menu.addAction(create_action)

        self.menu.addSeparator()
        settings_action = QAction("Settings…", self.menu)
        settings_action.triggered.connect(controller.open_settings)
        self.menu.addAction(settings_action)

        quit_action = QAction("Quit Winter", self.menu)
        quit_action.triggered.connect(self._quit)
        self.menu.addAction(quit_action)

        self.icon.setContextMenu(self.menu)
        self.icon.show()

        self.bus.status_message.connect(self.set_status)
        self.bus.listening_started.connect(lambda: self.set_status("Listening…"))
        self.bus.transcript_ready.connect(lambda t: self.set_status(f"Heard: {t}"))
        self.bus.intent_executed.connect(self.set_status)
        self.bus.error.connect(lambda e: self.set_status(f"⚠ {e}"))

    def refresh_characters(self) -> None:
        """(Re)build the character picker — call after one is added or removed."""
        self._char_menu.clear()
        for action in list(self._char_group.actions()):
            self._char_group.removeAction(action)
        active_id = self.controller.characters.active.id
        for character in self.controller.characters.list():
            action = QAction(character.display_name, self._char_menu)
            action.setCheckable(True)
            action.setChecked(character.id == active_id)
            action.triggered.connect(
                lambda _checked, cid=character.id:
                    self.controller.switch_character(cid)
            )
            self._char_group.addAction(action)
            self._char_menu.addAction(action)

    def set_status(self, text: str) -> None:
        text = text.strip()
        self._status.setText(text[:64] if text else "Idle")
        self.icon.setToolTip(f"Winter — {text}" if text else "Winter")

    def set_camera_enabled(self, enabled: bool) -> None:
        """Reflect camera state back into the checkbox without re-firing."""
        self._camera.blockSignals(True)
        self._camera.setChecked(enabled)
        self._camera.blockSignals(False)

    def set_camera_available(self, available: bool) -> None:
        self._camera.setEnabled(available)
        if not available:
            self._camera.setText("Camera commands (Phase 4)")

    def set_visualizer_checked(self, shown: bool) -> None:
        """Reflect visualizer visibility back into the checkbox without re-firing."""
        self._visualizer.blockSignals(True)
        self._visualizer.setChecked(shown)
        self._visualizer.blockSignals(False)

    def _quit(self) -> None:
        app = QApplication.instance()
        if app:
            app.quit()
