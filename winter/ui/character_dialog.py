"""Dialog for creating a new character.

Collects a name, wake word, personality, and optional sprite image and voice
clip, then hands them to the controller — which writes the character folder
and switches to it. The architecture already treats every character as a
drop-in folder, so this is just a friendly front-end for that.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (QApplication, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QLabel, QLineEdit,
                             QPlainTextEdit, QPushButton, QVBoxLayout)


def _voice_clip_hint() -> str:
    """The note under the voice-clip picker — flags when voice cloning isn't
    installed, so an uploaded clip isn't silently ignored at speak time."""
    from winter.audio.voice_env import voice_python

    if voice_python() is None:
        return ("Voice cloning isn't set up — run scripts/setup_voice.py to "
                "enable it. Until then a clip is saved with the character, "
                "but it speaks in the default voice.")
    return ("A clip of the voice to clone. Skip it and the character uses the "
            "fast default voice.")


class CreateCharacterDialog(QDialog):
    """Collects character details and asks the controller to create it."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._sprite_path: Optional[Path] = None
        self._voice_path: Optional[Path] = None
        self.setWindowTitle("Create a Character")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Hu Tao")
        self._name.textChanged.connect(self._suggest_wake_word)
        form.addRow("Name", self._name)

        self._wake = QLineEdit()
        self._wake.setPlaceholderText("e.g. Hey Hu Tao")
        form.addRow("Wake word", self._wake)
        form.addRow("", self._hint(
            "The phrase that activates this character. Use ordinary English "
            "words — the speech recognizer needs to know them."
        ))

        self._personality = QPlainTextEdit()
        self._personality.setPlaceholderText(
            "Describe how this character talks and behaves — this is its "
            "personality. Replies are spoken aloud, so ask it to keep them short."
        )
        self._personality.setMinimumHeight(96)
        form.addRow("Personality", self._personality)

        self._sprite_btn = QPushButton("Choose image…")
        self._sprite_btn.clicked.connect(self._choose_sprite)
        form.addRow("Sprite (optional)", self._sprite_btn)

        self._voice_btn = QPushButton("Choose audio or video…")
        self._voice_btn.clicked.connect(self._choose_voice)
        form.addRow("Voice clip (optional)", self._voice_btn)
        form.addRow("", self._hint(_voice_clip_hint()))

        self._status = self._hint("")
        layout.addWidget(self._status)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create")
        self._buttons.accepted.connect(self._create)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: gray; font-size: 11px;")
        return label

    def _suggest_wake_word(self, name: str) -> None:
        """Keep the wake word as 'Hey <name>' until the user edits it."""
        if not self._wake.isModified():
            name = name.strip()
            self._wake.setText(f"Hey {name}" if name else "")

    def _choose_sprite(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a sprite image", str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)",
        )
        if path:
            self._sprite_path = Path(path)
            self._sprite_btn.setText(self._sprite_path.name)

    def _choose_voice(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a voice clip (audio or video)", str(Path.home()),
            "Audio or video (*.wav *.mp3 *.m4a *.flac *.ogg *.aac "
            "*.mov *.mp4 *.m4v *.avi *.mkv *.webm)",
        )
        if path:
            self._voice_path = Path(path)
            self._voice_btn.setText(self._voice_path.name)

    def _create(self) -> None:
        name = self._name.text().strip()
        if not name:
            self._status.setText("Please enter a name.")
            return
        self._buttons.setEnabled(False)
        self._status.setText("Creating character…")
        QApplication.processEvents()  # let the status show during extraction
        try:
            self.controller.create_character(
                name=name,
                wake_word=self._wake.text().strip(),
                personality=self._personality.toPlainText().strip(),
                sprite_src=self._sprite_path,
                voice_src=self._voice_path,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self._buttons.setEnabled(True)
            self._status.setText(f"Couldn't create it — {exc}")
            return
        self.accept()
