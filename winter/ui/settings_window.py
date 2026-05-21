"""Settings window — configure Winter without hand-editing settings.yaml."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                             QPushButton, QSpinBox, QVBoxLayout)

from winter.config.character import CUSTOM_SPRITE


def install_sprite_image(character, source: Path) -> Path:
    """Install a user-chosen image as the character's custom sprite override
    (custom.png). The developer-placed default images are left untouched.
    Returns the written path."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage

    image = QImage(str(source))
    if image.isNull():
        raise ValueError("not a readable image file")
    max_dim = 1024  # keep the stored sprite a sensible size
    if image.width() > max_dim or image.height() > max_dim:
        image = image.scaled(
            max_dim, max_dim,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    if character.sprite_dir is None:
        raise ValueError("character has no sprite folder")
    character.sprite_dir.mkdir(parents=True, exist_ok=True)
    dest = character.sprite_dir / CUSTOM_SPRITE
    if not image.save(str(dest), "PNG"):
        raise IOError(f"could not write {dest}")
    return dest


def clear_sprite_images(character) -> bool:
    """Remove only the user's custom sprite override, so the character reverts
    to its default (developer-placed) images. Returns True if one was removed."""
    if character.sprite_dir is None:
        return False
    custom = character.sprite_dir / CUSTOM_SPRITE
    if custom.exists():
        custom.unlink()
        return True
    return False


def _input_devices() -> list[tuple[str, object]]:
    """(label, index) for input-capable audio devices; index None = default."""
    devices: list[tuple[str, object]] = [("System default", None)]
    try:
        import sounddevice as sd

        for index, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0:
                devices.append((dev["name"], index))
    except Exception:  # noqa: BLE001
        pass
    return devices


class SettingsWindow(QDialog):
    """A modeless settings dialog backed by the live Settings object."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.settings = controller.settings
        self.setWindowTitle("Winter — Settings")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._character = QComboBox()
        for character in controller.characters.list():
            self._character.addItem(character.display_name, character.id)
        self._character.setCurrentIndex(
            max(0, self._character.findData(controller.characters.active.id))
        )
        form.addRow("Character", self._character)

        self._mic = QComboBox()
        for label, index in _input_devices():
            self._mic.addItem(label, index)
        self._mic.setCurrentIndex(
            max(0, self._mic.findData(self.settings.audio.input_device))
        )
        form.addRow("Microphone", self._mic)

        self._camera = QSpinBox()
        self._camera.setRange(0, 8)
        self._camera.setValue(self.settings.camera.index)
        form.addRow("Camera index", self._camera)

        self._stt = QComboBox()
        for model in ("tiny.en", "base.en", "small.en", "small", "medium"):
            self._stt.addItem(model)
        if self._stt.findText(self.settings.stt.model) < 0:
            self._stt.addItem(self.settings.stt.model)
        self._stt.setCurrentText(self.settings.stt.model)
        form.addRow("Speech model", self._stt)

        self._size = QSpinBox()
        self._size.setRange(100, 360)
        self._size.setSingleStep(10)
        self._size.setValue(self.settings.visualizer.size)
        form.addRow("Sprite size", self._size)

        self._sprite_button = QPushButton("Choose image…")
        self._sprite_button.clicked.connect(self._choose_sprite)
        self._reset_button = QPushButton("Reset to default")
        self._reset_button.clicked.connect(self._reset_sprite)
        sprite_row = QHBoxLayout()
        sprite_row.addWidget(self._sprite_button)
        sprite_row.addWidget(self._reset_button)
        form.addRow("Sprite image", sprite_row)
        self._sprite_status = QLabel("")
        self._sprite_status.setWordWrap(True)
        self._sprite_status.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow("", self._sprite_status)
        # the sprite controls are only offered for characters that allow it
        self._character.currentIndexChanged.connect(self._update_sprite_buttons)
        self._update_sprite_buttons()

        self._echo = QCheckBox("Cancel playing audio from the mic (dims audio)")
        self._echo.setChecked(self.settings.audio.echo_cancellation)
        form.addRow("Echo cancellation", self._echo)

        self._duck = QCheckBox("Lower the volume briefly while listening")
        self._duck.setChecked(self.settings.audio.duck_while_listening)
        form.addRow("Duck while listening", self._duck)

        note = QLabel("Microphone, camera, speech model and echo-cancellation "
                      "changes take effect after restarting Winter.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_sprite_buttons(self) -> None:
        """Enable the sprite controls only for characters that allow them;
        'Reset' only when there is a custom sprite to clear."""
        character = self.controller.characters.get(self._character.currentData())
        editable = bool(character and character.sprite_editable)
        has_custom = bool(character and character.has_custom_sprite)
        self._sprite_button.setEnabled(editable)
        self._reset_button.setEnabled(editable and has_custom)
        self._sprite_status.setText(
            "" if editable else "This character's sprite is fixed."
        )

    def _refresh_active_sprite(self, char_id: str) -> None:
        if char_id == self.controller.characters.active.id:
            self.controller.visualizer.set_character(
                self.controller.characters.active
            )

    def _choose_sprite(self) -> None:
        """Let the user pick an image file to use as the selected character's
        sprite. Applies immediately (not deferred to Save)."""
        char_id = self._character.currentData()
        character = self.controller.characters.get(char_id)
        if character is None or not character.sprite_editable:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, f"Choose a sprite image for {character.display_name}",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)",
        )
        if not path:
            return
        try:
            install_sprite_image(character, Path(path))
        except Exception as exc:  # noqa: BLE001
            self._sprite_status.setText(f"Couldn't use that image — {exc}")
            return
        self._refresh_active_sprite(char_id)
        self._update_sprite_buttons()
        self._sprite_status.setText(f"Sprite updated for {character.display_name}.")

    def _reset_sprite(self) -> None:
        """Remove the custom sprite so the character reverts to the built-in
        code-drawn sprite."""
        char_id = self._character.currentData()
        character = self.controller.characters.get(char_id)
        if character is None or not character.sprite_editable:
            return
        clear_sprite_images(character)
        self._refresh_active_sprite(char_id)
        self._update_sprite_buttons()
        self._sprite_status.setText(
            f"{character.display_name}'s sprite reset to default."
        )

    def _save(self) -> None:
        s = self.settings
        s.audio.input_device = self._mic.currentData()
        s.audio.echo_cancellation = self._echo.isChecked()
        s.audio.duck_while_listening = self._duck.isChecked()
        s.camera.index = self._camera.value()
        s.stt.model = self._stt.currentText()
        s.visualizer.size = self._size.value()

        chosen = self._character.currentData()
        if chosen and chosen != self.controller.characters.active.id:
            self.controller.switch_character(chosen)

        try:
            s.save()
        except Exception as exc:  # noqa: BLE001
            print("[settings] save failed:", exc)
        self.controller.bus.status_message.emit("Settings saved.")
        self.accept()
