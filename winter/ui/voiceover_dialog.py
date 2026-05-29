"""Modal dialog: paste/load a script, pick a voice, render a WAV voiceover.

Reuses the cloning engine Winter already runs for character voices. The dialog
owns no models itself — it asks the AppController for a long-lived
`VoiceoverRenderer` and receives progress over Qt signals, so closing the
dialog mid-render is safe and the render keeps going in the background.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout,
                             QLabel, QLineEdit, QProgressBar, QPushButton,
                             QTextEdit, QVBoxLayout)

_OUTPUT_DIR = Path.home() / "Documents" / "Winter Voiceovers"
_REFERENCE_OPTION = "__reference__"


class VoiceoverDialog(QDialog):
    """The 'Generate Voiceover' UI."""

    def __init__(self, controller, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Generate Voiceover")
        self.resize(580, 500)
        self._reference_path: Optional[Path] = None
        self._build_ui()
        self._wire_renderer()
        if not self._voice_cloning_available():
            self._status.setText(
                "Voice cloning isn't set up — run scripts/setup_voice.py to "
                "enable it."
            )
            self._generate.setEnabled(False)

    @staticmethod
    def _voice_cloning_available() -> bool:
        from winter.audio.voice_env import voice_python
        return voice_python() is not None

    # ----- build the UI -----
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Script"))
        self._script = QTextEdit()
        self._script.setPlaceholderText(
            "Paste the script you want narrated — or click 'Load file…'."
        )
        layout.addWidget(self._script)

        load_row = QHBoxLayout()
        load_row.addStretch(1)
        load_btn = QPushButton("Load file…")
        load_btn.clicked.connect(self._load_file)
        load_row.addWidget(load_btn)
        layout.addLayout(load_row)

        # voice picker — characters with a cloned voice + 'Upload reference'
        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Voice"))
        self._voice = QComboBox()
        for character in self.controller.characters.list():
            if character.has_voice_reference:
                self._voice.addItem(character.display_name, character.id)
        self._voice.addItem("Upload reference clip…", _REFERENCE_OPTION)
        self._voice.currentIndexChanged.connect(self._on_voice_changed)
        voice_row.addWidget(self._voice, 1)
        layout.addLayout(voice_row)
        self._voice_status = QLabel("")
        self._voice_status.setStyleSheet("color: #888;")
        layout.addWidget(self._voice_status)

        # output picker
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Save to"))
        self._output = QLineEdit(str(_OUTPUT_DIR / "voiceover.wav"))
        out_row.addWidget(self._output, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._pick_output)
        out_row.addWidget(browse)
        layout.addLayout(out_row)

        # progress + status
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # buttons
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        self._generate = QPushButton("Generate")
        self._generate.setDefault(True)
        self._generate.clicked.connect(self._on_generate)
        bottom.addWidget(self._generate)
        layout.addLayout(bottom)

    def _wire_renderer(self) -> None:
        renderer = self.controller.ensure_voiceover_renderer()
        renderer.progress.connect(self._on_progress)
        renderer.finished_ok.connect(self._on_finished)
        renderer.failed.connect(self._on_failed)

    def closeEvent(self, event) -> None:
        """Disconnect from the long-lived renderer so its signals don't fire
        into a destroyed dialog after we close."""
        try:
            renderer = self.controller.ensure_voiceover_renderer()
        except Exception:  # noqa: BLE001
            renderer = None
        if renderer is not None:
            for sig, slot in ((renderer.progress, self._on_progress),
                              (renderer.finished_ok, self._on_finished),
                              (renderer.failed, self._on_failed)):
                try:
                    sig.disconnect(slot)
                except TypeError:
                    pass  # already disconnected
        super().closeEvent(event)

    # ----- handlers -----
    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load script", str(Path.home()),
            "Text (*.txt *.md);;Any (*)",
        )
        if path:
            try:
                self._script.setPlainText(Path(path).read_text(encoding="utf-8"))
            except OSError as exc:
                self._status.setText(f"Couldn't read that file — {exc}")

    def _on_voice_changed(self, _index: int) -> None:
        if self._voice.currentData() == _REFERENCE_OPTION:
            self._pick_reference()
        else:
            self._reference_path = None
            self._voice_status.setText("")

    def _pick_reference(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a voice clip (audio or video)", str(Path.home()),
            "Audio or video (*.wav *.mp3 *.m4a *.flac *.ogg *.aac "
            "*.mov *.mp4 *.m4v *.avi *.mkv *.webm)",
        )
        if not path:
            if self._voice.count() > 1:
                self._voice.setCurrentIndex(0)  # revert to a real voice
            return
        try:
            from winter.config.character import _extract_audio
            fd, tmp = tempfile.mkstemp(prefix="winter_vo_ref_", suffix=".wav")
            os.close(fd)
            _extract_audio(Path(path), Path(tmp))
            self._reference_path = Path(tmp)
            self._voice_status.setText(f"Cloning from: {Path(path).name}")
        except Exception as exc:  # noqa: BLE001 - shown to user
            self._voice_status.setText(f"Couldn't read that clip — {exc}")
            if self._voice.count() > 1:
                self._voice.setCurrentIndex(0)

    def _pick_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save voiceover as", self._output.text(), "WAV (*.wav)",
        )
        if path:
            if not path.lower().endswith(".wav"):
                path += ".wav"
            self._output.setText(path)

    def _on_generate(self) -> None:
        text = self._script.toPlainText().strip()
        if not text:
            self._status.setText("The script is empty.")
            return
        try:
            output = Path(self._output.text()).expanduser()
            if not output.suffix:
                output = output.with_suffix(".wav")
            output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._status.setText(f"Bad output path — {exc}")
            return
        reference, params = self._selected_voice()
        if reference is None:
            self._status.setText("Pick a voice first.")
            return
        self._set_busy(True)
        self._status.setText(
            "Loading the voice model… (takes ~30s the first time, then it "
            "stays warm for the rest of the session.)"
        )
        renderer = self.controller.ensure_voiceover_renderer()
        renderer.render(text, reference, params, output)

    def _selected_voice(self) -> tuple[Optional[Path], dict]:
        data = self._voice.currentData()
        if data == _REFERENCE_OPTION:
            return self._reference_path, {}
        for character in self.controller.characters.list():
            if character.id == data:
                return character.voice_reference, dict(character.tts)
        return None, {}

    def _set_busy(self, busy: bool) -> None:
        self._generate.setEnabled(not busy)
        self._progress.setVisible(busy)
        if busy:
            self._progress.setRange(0, 0)  # indeterminate until first chunk

    # ----- renderer signals -----
    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)
        self._status.setText(f"Rendering chunk {done} of {total}…")

    def _on_finished(self, path: str) -> None:
        self._set_busy(False)
        self._status.setText(f"Saved: {path}")
        # reveal the file in the OS file manager so it's easy to find
        try:
            from winter.system.osinfo import IS_MACOS, IS_WINDOWS
            if IS_MACOS:
                subprocess.Popen(["open", "-R", path])
            elif IS_WINDOWS:
                subprocess.Popen(["explorer", f"/select,{path}"])
        except Exception:  # noqa: BLE001 - best effort
            pass

    def _on_failed(self, error: str) -> None:
        self._set_busy(False)
        self._status.setText(f"⚠ {error}")
