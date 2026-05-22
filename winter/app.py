"""AppController — owns every service and routes signals between them."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QThreadPool

from winter.audio import sounds
from winter.audio.capture import AudioCaptureThread
from winter.audio.stt import STTEngine
from winter.audio.tts_thread import TTSThread
from winter.audio.wakeword import VoskWakeWordEngine, WakeWordEngine
from winter.brain.llm import OllamaClient
from winter.brain.router import IntentRouter, RouteResult
from winter.brain.websearch import DdgsProvider
from winter.config.character import CharacterManager
from winter.config.settings import Settings
from winter.core.events import EventBus
from winter.core.state import AppState, Phase
from winter.core.worker import Worker
from winter.system import control, cursor, permissions
from winter.updater import apply_update, check_for_update, relaunch
from winter.ui.character_dialog import CreateCharacterDialog
from winter.ui.settings_window import SettingsWindow
from winter.ui.tray import TrayController
from winter.ui.visualizer import VisualizerWidget
from winter.vision.camera import CameraThread

_SCROLL_LINES = 10   # wheel lines per scroll-gesture flick (tune for Shorts)


class AppController(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings.load()
        self.characters = CharacterManager()
        self.characters.set_active(self.settings.active_character)

        self.bus = EventBus()
        self.state = AppState(
            voice_enabled=self.settings.voice_enabled,
            camera_enabled=self.settings.camera_enabled,
            active_character=self.characters.active.id,
        )
        self.pool = QThreadPool.globalInstance()
        self._workers: set[Worker] = set()

        # brain
        self.llm = OllamaClient(self.settings.llm.model, self.settings.llm.host)
        self.websearch = DdgsProvider()
        self.router = IntentRouter(self.llm, self.websearch, self.bus)

        # heavy / lazily-built pieces
        self.stt: Optional[STTEngine] = None
        self._wake_engine: Optional[WakeWordEngine] = None
        self.audio_thread: Optional[AudioCaptureThread] = None
        self.camera_thread: Optional[CameraThread] = None
        # TTS lives on its own thread — a torch/MPS model must stay on one thread
        self.tts_thread = TTSThread(self.bus)
        self._tts_ready = False

        # ui
        self.tray = TrayController(self)
        self.visualizer = VisualizerWidget(
            self.settings, on_move=self._on_visualizer_moved,
        )
        self.visualizer.set_character(self.characters.active)
        self._settings_window: Optional[SettingsWindow] = None

        self._wire()

    # ------------------------------------------------------------------ setup
    def _wire(self) -> None:
        self.bus.wake_word_detected.connect(self._on_wake)
        self.bus.command_audio_ready.connect(self._on_command_audio)
        self.bus.transcript_ready.connect(self._on_transcript)
        self.bus.tts_ready.connect(self._on_tts_ready)
        self.bus.tts_started.connect(self._on_tts_started)
        self.bus.tts_finished.connect(self._on_tts_finished)
        self.bus.audio_level.connect(self.visualizer.set_level)
        self.bus.cursor_target.connect(self._on_cursor_target)
        self.bus.gesture_detected.connect(self._on_gesture)
        self.bus.error.connect(self._on_error)

    def start(self) -> None:
        self.tray.set_camera_available(True)
        if self.settings.visualizer.enabled:
            self.visualizer.show_orb()
        if self.state.camera_enabled:
            self._start_camera()
        if not permissions.accessibility_trusted():
            permissions.prompt_accessibility()  # register Winter + show dialog
        for hint in permissions.permission_hints():
            print("[permissions]", hint)
            self.bus.status_message.emit(hint)
        self.bus.status_message.emit("Warming up models…")
        self.tts_thread.start()  # builds the voice engine on its own thread
        self._warm_models()
        self.check_for_updates()  # quietly check GitHub for a newer version

    # ----------------------------------------------------------------- phase
    def _set_phase(self, phase: Phase) -> None:
        """Update app phase and tint the visualizer to match."""
        self.state.phase = phase
        self.visualizer.set_state(phase.name.lower())

    # ------------------------------------------------------------- visualizer
    def set_visualizer_visible(self, visible: bool) -> None:
        if visible:
            self.visualizer.show_orb()
        else:
            self.visualizer.hide()
        self.settings.visualizer.enabled = visible
        self.tray.set_visualizer_checked(visible)

    def _on_visualizer_moved(self, x: int, y: int) -> None:
        self.settings.visualizer.x = x
        self.settings.visualizer.y = y

    # ------------------------------------------------------------- settings UI
    def open_settings(self) -> None:
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self)
            self._settings_window.finished.connect(self._on_settings_closed)
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _on_settings_closed(self, _result: int) -> None:
        self._settings_window = None

    def open_create_character(self) -> None:
        """Open the modal 'Create a Character' dialog."""
        CreateCharacterDialog(self).exec()

    # ---------------------------------------------------------------- updates
    def check_for_updates(self, announce_uptodate: bool = False) -> None:
        """Check GitHub for a newer version of Winter, on a worker thread."""
        self._announce_uptodate = announce_uptodate
        if announce_uptodate:
            self.bus.status_message.emit("Checking for updates…")
        self._run(check_for_update, on_result=self._on_update_check)

    def _on_update_check(self, available: bool) -> None:
        self.tray.set_update_available(available)
        if available:
            self.bus.status_message.emit(
                "An update is available — open the menu to install it."
            )
        elif getattr(self, "_announce_uptodate", False):
            self.bus.status_message.emit("Winter is up to date.")
        self._announce_uptodate = False

    def install_update(self) -> None:
        """Pull and install the latest version, then offer to restart."""
        self.bus.status_message.emit(
            "Installing update — this may take a minute…"
        )
        self._run(apply_update, on_result=self._on_update_installed,
                  on_error=self._on_update_failed)

    def _on_update_installed(self, _result) -> None:
        from PyQt6.QtWidgets import QApplication, QMessageBox

        self.tray.set_update_available(False)
        answer = QMessageBox.question(
            None, "Winter updated",
            "Winter has been updated. Restart it now to use the new version?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            relaunch()
            app = QApplication.instance()
            if app is not None:
                app.quit()

    def _on_update_failed(self, error) -> None:
        self.bus.status_message.emit(f"Update failed — {error}")

    # ------------------------------------------------------------- worker util
    def _run(self, fn: Callable, on_result: Optional[Callable] = None,
             on_error: Optional[Callable] = None, *args) -> None:
        worker = Worker(fn, *args)
        self._workers.add(worker)
        if on_result:
            worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error or self._on_error)
        worker.signals.finished.connect(lambda w=worker: self._workers.discard(w))
        self.pool.start(worker)

    # ----------------------------------------------------------- model warmup
    def _warm_models(self) -> None:
        def load() -> dict:
            result: dict = {"stt": STTEngine(
                self.settings.stt.model,
                self.settings.stt.compute_type,
                self.settings.stt.language,
            )}
            self.llm.warm_up()
            if self.settings.voice_enabled:
                result["wake"] = self._build_wake_engine()
            return result

        self._run(load, on_result=self._on_warm_done)

    def _on_warm_done(self, result: dict) -> None:
        self.stt = result.get("stt")
        if result.get("wake") is not None:
            self._wake_engine = result["wake"]
        self.bus.status_message.emit("Ready.")
        if self.state.voice_enabled and self._wake_engine is not None:
            self._launch_audio_thread()

    def _build_wake_engine(self) -> WakeWordEngine:
        return VoskWakeWordEngine(self.characters.active.wake_word)

    # --------------------------------------------------------------- voice I/O
    def set_voice_enabled(self, enabled: bool) -> None:
        self.state.voice_enabled = enabled
        if enabled:
            self._start_voice()
        else:
            self._stop_voice()
        self.bus.state_changed.emit()

    def _start_voice(self) -> None:
        if self._wake_engine is None:
            self.bus.status_message.emit("Loading wake word…")
            self._run(self._build_wake_engine, on_result=self._on_wake_engine_ready)
            return
        self._launch_audio_thread()

    def _on_wake_engine_ready(self, engine: WakeWordEngine) -> None:
        self._wake_engine = engine
        if self.state.voice_enabled:
            self._launch_audio_thread()

    def _launch_audio_thread(self) -> None:
        if self.audio_thread is None:
            self.audio_thread = AudioCaptureThread(
                self.bus, self.settings, self._wake_engine,
            )
        if not self.audio_thread.isRunning():
            self.audio_thread.set_enabled(True)
            self.audio_thread.start()
        self.bus.status_message.emit(
            f"Listening for “{self.characters.active.wake_word}”."
        )

    def _stop_voice(self) -> None:
        if self.audio_thread and self.audio_thread.isRunning():
            self.audio_thread.stop()
        self.bus.status_message.emit("Voice commands off.")

    # ----------------------------------------------------------------- camera
    def set_camera_enabled(self, enabled: bool) -> None:
        self.state.camera_enabled = enabled
        if enabled:
            self._start_camera()
        else:
            self._stop_camera()
        self.bus.state_changed.emit()

    def _start_camera(self) -> None:
        if self.camera_thread and self.camera_thread.isRunning():
            return
        # camera permission must be requested on the main thread (here),
        # never from inside the camera thread
        if not permissions.camera_authorized():
            if permissions.camera_access_undecided():
                permissions.request_camera_access()
                self.bus.status_message.emit(
                    "Allow camera access, then turn Camera commands on again."
                )
            else:
                self.bus.status_message.emit(
                    "Camera access denied — enable it in System Settings → "
                    "Privacy & Security → Camera."
                )
            self.state.camera_enabled = False
            self.tray.set_camera_enabled(False)
            return
        if not permissions.accessibility_trusted():
            self.bus.status_message.emit(
                "Camera commands need Accessibility — switch on Winter in "
                "System Settings → Privacy & Security → Accessibility, then "
                "restart Winter."
            )
        self.camera_thread = CameraThread(self.bus, self.settings)
        self.camera_thread.start()

    def _stop_camera(self) -> None:
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
        self.camera_thread = None
        self.bus.status_message.emit("Camera gestures off.")

    # ----------------------------------------------------- camera gesture I/O
    def _on_cursor_target(self, x: float, y: float) -> None:
        cursor.move_to(x, y)

    def _on_gesture(self, name: str) -> None:
        if name == "click":
            cursor.click()
        elif name == "swipe_right":
            control.media("next")
            self.bus.status_message.emit("Swipe → next")
        elif name == "swipe_left":
            control.media("previous")
            self.bus.status_message.emit("Swipe → previous")
        elif name == "scroll_up":
            cursor.scroll(_SCROLL_LINES)
            self.bus.status_message.emit("Scroll up")
        elif name == "scroll_down":
            cursor.scroll(-_SCROLL_LINES)
            self.bus.status_message.emit("Scroll down")

    # -------------------------------------------------------------- character
    def switch_character(self, char_id: str) -> None:
        character = self.characters.set_active(char_id)
        self.state.active_character = character.id
        self.bus.status_message.emit(f"Switched to {character.display_name}.")
        self.bus.character_changed.emit(character.id)
        self.visualizer.set_character(character)  # swap to its sprite art
        self._prime_tts_voice()  # pre-load the new character's voice

        # the wake engine listens for one fixed phrase — if the new character
        # uses a different wake word, tear it and the audio thread down
        if (self._wake_engine is not None
                and self._wake_engine.model_name != character.wake_word):
            if self.audio_thread:
                self.audio_thread.stop()
            self.audio_thread = None
            self._wake_engine = None
        # (re)start voice for the new character — idempotent when it is already
        # running with the right wake word, and recovers it if it had stopped
        if self.state.voice_enabled and self.stt is not None:
            self._start_voice()
        self.bus.state_changed.emit()

    def create_character(self, name: str, wake_word: str, personality: str,
                         sprite_src: Optional[Path] = None,
                         voice_src: Optional[Path] = None):
        """Create a new character, switch to it, and refresh the menu."""
        character = self.characters.create(
            name, wake_word, personality, sprite_src, voice_src
        )
        self.switch_character(character.id)
        self.tray.refresh_characters()
        self.bus.status_message.emit(f"Created {character.display_name}.")
        return character

    def delete_character(self, char_id: str) -> bool:
        """Delete a character; fall back to the default if it was active."""
        was_active = self.characters.active.id == char_id
        if not self.characters.delete(char_id):
            return False
        if was_active:
            self.switch_character(self.characters.active.id)
        self.tray.refresh_characters()
        self.bus.status_message.emit("Character deleted.")
        return True

    # ------------------------------------------------------------ voice steps
    def _on_wake(self, name: str) -> None:
        self._set_phase(Phase.LISTENING)
        sounds.play_chime()
        self.bus.status_message.emit("Listening…")

    def _on_command_audio(self, audio) -> None:
        self._set_phase(Phase.THINKING)
        if self.stt is None:
            self.bus.intent_executed.emit("Still warming up — try again shortly.")
            self._set_phase(Phase.IDLE)
            return
        self.bus.status_message.emit("Thinking…")
        self._run(self._process_command, self._on_command_result, None, audio)

    def _process_command(self, audio) -> tuple[str, RouteResult]:
        text = self.stt.transcribe(audio)
        print(f"[heard] {text!r}")
        if not text:
            return "", RouteResult("I didn't catch that — try again.")
        self.bus.transcript_ready.emit(text)
        result = self.router.handle(text, self.characters.active)
        print(f"[result] {result.display}")
        return text, result

    def _on_command_result(self, payload: tuple[str, RouteResult]) -> None:
        text, result = payload
        self.state.last_transcript = text
        self.state.last_result = result.display
        if text:
            self.bus.intent_executed.emit(f"“{text}” → {result.display}")
        else:
            self.bus.intent_executed.emit(result.display)
        if result.speak:
            self._speak(result.speak)
        else:
            self._set_phase(Phase.IDLE)

    # ----------------------------------------------------------------- speech
    def _speak(self, text: str) -> None:
        if not self._tts_ready:
            self._set_phase(Phase.IDLE)
            return
        self._set_phase(Phase.SPEAKING)
        character = self.characters.active
        reference = character.voice_reference if character.has_voice_reference else None
        # synthesis + playback happen on the dedicated TTS thread
        self.tts_thread.speak(text, reference, character.tts)

    def _on_tts_ready(self, ok: bool) -> None:
        self._tts_ready = ok
        if ok:
            self._prime_tts_voice()
        else:
            self.bus.status_message.emit("Voice replies unavailable.")

    def _prime_tts_voice(self) -> None:
        """Pre-load the active character's voice so the slow conditioning step
        runs once now, not on every spoken reply."""
        if not self._tts_ready:
            return
        character = self.characters.active
        reference = character.voice_reference if character.has_voice_reference else None
        self.tts_thread.prepare(reference, character.tts)

    def _on_tts_started(self) -> None:
        if self.audio_thread:
            self.audio_thread.set_suppressed(True)  # don't hear our own voice

    def _on_tts_finished(self) -> None:
        if self.audio_thread:
            self.audio_thread.set_suppressed(False)
        self._set_phase(Phase.IDLE)

    def _on_transcript(self, text: str) -> None:
        self.state.last_transcript = text

    def _on_error(self, message: str) -> None:
        self._set_phase(Phase.IDLE)
        print("[error]", message)

    # ----------------------------------------------------------------- teardown
    def shutdown(self) -> None:
        if self.audio_thread:
            self.audio_thread.stop()
        if self.camera_thread:
            self.camera_thread.stop()
        self.tts_thread.stop()
        self.settings.voice_enabled = self.state.voice_enabled
        self.settings.camera_enabled = self.state.camera_enabled
        self.settings.active_character = self.characters.active.id
        try:
            self.settings.save()
        except Exception as exc:  # noqa: BLE001
            print("[error] could not save settings:", exc)
