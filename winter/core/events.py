"""Central signal bus. Every cross-thread message goes through here."""
from PyQt6.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    # --- voice pipeline ---
    wake_word_detected = pyqtSignal(str)        # model name that fired
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()
    command_audio_ready = pyqtSignal(object)    # np.ndarray int16 mono 16kHz
    transcript_ready = pyqtSignal(str)
    intent_executed = pyqtSignal(str)           # human-readable result

    # --- replies / TTS (Phase 2) ---
    reply_ready = pyqtSignal(str)
    tts_ready = pyqtSignal(bool)                # voice engine loaded (ok/failed)
    tts_started = pyqtSignal()
    tts_finished = pyqtSignal()
    audio_level = pyqtSignal(float)             # 0-1, drives the visualizer

    # --- vision (Phase 4) ---
    gesture_detected = pyqtSignal(str)
    cursor_target = pyqtSignal(float, float)

    # --- app lifecycle ---
    state_changed = pyqtSignal()
    character_changed = pyqtSignal(str)
    status_message = pyqtSignal(str)
    error = pyqtSignal(str)
